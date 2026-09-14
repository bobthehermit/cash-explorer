"""
lib/data.py -- where the parquet comes from, and nothing else.

The app never touches a path or a URL directly; it asks this module for a
table by name. Two sources:

  local   a directory holding what publish.py writes (cash_lines.parquet, ...)
          or, as a fallback, the extractor's raw partitioned tree
          (cash_lines/fy=2026/data.parquet, ...). Either shape works.

  gdrive  the same flat files, downloaded by Google Drive file ID through the
          public export URL -- the pattern the OBMS explorer uses. IDs live in
          gdrive_manifest.json at the repo root. Downloads are cached on disk
          for the life of the container, so a Space restart re-downloads once
          and every session after that reads locally.

Configuration is resolved in this order, first hit wins:

  1. environment variables  CASH_DATA_SOURCE, CASH_DATA_DIR
  2. st.secrets              (a local .streamlit/secrets.toml)
  3. defaults: "gdrive" if gdrive_manifest.json has real IDs, otherwise
     "local" pointing at ./sample_data/cash_data  (python sample_data/make_sample.py)

Column contract: the loader SELECTS columns (cash_lines is ~1.7M rows x 30
columns and source_path alone is ~170 MB of repeated strings in memory) but
never renames them. Add a column to COLS when a view needs it.
"""

import json
import os
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pyarrow.parquet as pq
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "gdrive_manifest.json"
SAMPLE_DIR = ROOT / "sample_data" / "cash_data"
CACHE_DIR = Path(tempfile.gettempdir()) / "cash-explorer"
PLACEHOLDER_RE = re.compile(r"^(PASTE|TODO|<)", re.I)

# Only the columns each view actually uses. None = every column.
COLS = {
    "cash_lines": ["EntityKey", "entity_name", "entity_folder", "FiscalYearKey",
                   "PeriodOrder", "fund_code", "line_no", "amount", "source_file"],
    "cash_bank": ["EntityKey", "FiscalYearKey", "PeriodOrder", "account_name",
                  "bank", "statement_balance", "net_outstanding_items",
                  "adjusted_bank_balance", "adjustment_desc", "adjustment_amount"],
    "cash_explanations": ["EntityKey", "FiscalYearKey", "PeriodOrder", "line_no",
                          "fund_code", "amount", "explanation"],
    "cash_manifest": None,
    "cash_coverage": None,
}


# ---------------------------------------------------------------- config

def _setting(name, default=None):
    """Env var first, then st.secrets, then the default."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:          # no secrets.toml at all is the normal case
        pass
    return default


def gdrive_ids():
    """table -> file ID, with placeholders dropped."""
    try:
        with open(MANIFEST_PATH) as f:
            raw = json.load(f)
    except Exception:
        return {}
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, str)
            and v.strip() and not PLACEHOLDER_RE.match(v.strip())}


def config():
    ids = gdrive_ids()
    source = _setting("CASH_DATA_SOURCE")
    if not source:
        source = "gdrive" if "cash_lines" in ids else "local"
    data_dir = Path(_setting("CASH_DATA_DIR", str(SAMPLE_DIR))).expanduser()
    return SimpleNamespace(source=source.lower(), data_dir=data_dir, ids=ids)


# ---------------------------------------------------------------- local

def _read_partitioned(base, want):
    """Read <base>/fy=*/data.parquet one partition at a time and concat in
    pandas. pyarrow's dataset reader refuses to unify a typed column against
    an all-null one across partitions; pandas concat does not care."""
    parts = []
    for sub in sorted(os.listdir(base)):
        f = os.path.join(base, sub, "data.parquet")
        if os.path.exists(f):
            parts.append(_read_file(f, want))
    return pd.concat(parts, ignore_index=True) if parts else None


def _read_file(path, want):
    if want:
        have = set(pq.ParquetFile(path).schema.names)
        use = [c for c in want if c in have]
        return pd.read_parquet(path, columns=use)
    return pd.read_parquet(path)


def _local_path(cfg, name):
    flat = cfg.data_dir / f"{name}.parquet"
    if flat.exists():
        return flat, False
    part = cfg.data_dir / name
    if part.is_dir():
        return part, True
    return None, False


# ---------------------------------------------------------------- gdrive

def _download(file_id, dest):
    """Fetch one Drive file by ID into dest.

    The uc?export=download URL streams small files directly. For files past
    Google's virus-scan threshold (~100 MB) it returns an HTML interstitial
    instead; the usercontent host with confirm=t skips that page. Either way
    we verify the result is parquet (magic bytes 'PAR1') before keeping it,
    because a permissions problem also comes back as HTML with status 200.
    """
    urls = [
        f"https://drive.google.com/uc?export=download&id={file_id}",
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
    ]
    last = None
    with requests.Session() as s:
        for url in urls:
            r = s.get(url, stream=True, timeout=300)
            if "text/html" in r.headers.get("content-type", ""):
                last = "Drive returned a web page instead of the file"
                r.close()
                continue
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            with open(tmp, "rb") as f:
                magic = f.read(4)
            if magic != b"PAR1":
                tmp.unlink(missing_ok=True)
                last = "downloaded content is not parquet"
                continue
            os.replace(tmp, dest)
            return dest
    raise RuntimeError(
        f"Could not download Drive file {file_id}: {last}. Is it shared as "
        f"'Anyone with the link', and is the ID in gdrive_manifest.json current?")


def _gdrive_path(cfg, name):
    fid = cfg.ids.get(name)
    if not fid:
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{name}_{fid}.parquet"
    if not dest.exists():
        _download(fid, dest)
    return dest


def clear_download_cache():
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            try:
                f.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------- public

def _tighten(df, name):
    """Cut memory: integer-ish keys downcast, repeated strings to category."""
    if df is None:
        return None
    for c in ("FiscalYearKey", "PeriodOrder", "fund_code", "line_no"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce", downcast="integer")
    if "amount" in df:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if name == "cash_lines":
        for c in ("EntityKey", "entity_name", "entity_folder"):
            if c in df:
                df[c] = df[c].astype("category")
    return df


@st.cache_data(show_spinner="Reading data...")
def load_table(name, _source, _data_dir, _ids_key):
    """Load one table. The underscored args exist only so the cache key
    changes when the configuration does; call through load() instead."""
    cfg = config()
    want = COLS.get(name)
    if cfg.source == "gdrive":
        p = _gdrive_path(cfg, name)
        df = _read_file(p, want) if p else None
    else:
        p, partitioned = _local_path(cfg, name)
        if p is None:
            df = None
        elif partitioned:
            df = _read_partitioned(p, want)
        else:
            df = _read_file(p, want)
    return _tighten(df, name)


def load(name):
    cfg = config()
    return load_table(name, cfg.source, str(cfg.data_dir),
                      "|".join(sorted(cfg.ids.values())))


def data_stamp():
    """publish_manifest.json if reachable: when the data was published, when
    it was extracted, which parser. Returns {} when unavailable."""
    cfg = config()
    try:
        if cfg.source == "gdrive":
            fid = cfg.ids.get("publish_manifest")
            if not fid:
                return {}
            r = requests.get(f"https://drive.google.com/uc?export=download&id={fid}",
                             timeout=30)
            r.raise_for_status()
            return r.json()
        p = cfg.data_dir / "publish_manifest.json"
        if p.exists():
            with open(p) as f:
                return json.load(f)
        p = cfg.data_dir / "extraction_metadata.json"
        if p.exists():
            with open(p) as f:
                return {"extraction": json.load(f)}
    except Exception:
        pass
    return {}


def describe_source():
    """One line for the sidebar."""
    cfg = config()
    if cfg.source == "gdrive":
        n = len([k for k in cfg.ids if k != "publish_manifest"])
        return f"Google Drive · {n} tables"
    return f"Local · {cfg.data_dir}"
