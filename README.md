---
title: SBB Cash Explorer
emoji: 🏦
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8501
pinned: false
---

# SBB Cash Explorer

Streamlit front end for the quarterly cash report data extracted from the
School Budget Bureau's SharePoint by the
[CashReports](https://github.com/bobthehermit/CashReports) pipeline.

Five views: **Portfolio** (statewide position and trend), **Entity** (one LEA
across years, fund detail, bank accounts), **Fund signs** (calibration of the
extractor's sign expectations), **Flags** (the review queue), **Coverage**
(who has not filed).

## Run it

```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python sample_data/make_sample.py                    # fabricated data, if you have no real parquet
streamlit run app.py
```

## Where the data comes from

`lib/data.py` is the only file that knows. It resolves, in order:

1. environment variables `CASH_DATA_SOURCE` (`local` | `gdrive`) and `CASH_DATA_DIR`
2. the same keys in `.streamlit/secrets.toml` (see `secrets.toml.example`)
3. defaults: `gdrive` if `gdrive_manifest.json` has real file IDs, else `local`
   pointing at `sample_data/cash_data`

| Source | What it reads |
|---|---|
| `local` | `CASH_DATA_DIR/<table>.parquet` as written by `publish.py`, or the extractor's partitioned `<table>/fy=NNNN/data.parquet` tree -- both shapes work |
| `gdrive` | each table by Google Drive file ID from `gdrive_manifest.json`, downloaded once per container into a temp cache |

On the work machine, `publish.py` mirrors the flat files into a Google Drive
for Desktop folder every night. `gdrive_manifest.json` maps table name → file
ID; because `publish.py` overwrites in place, the IDs do not change between
runs. If a file is ever deleted and re-created in Drive, update its ID here.

Drive files must be shared as **Anyone with the link** for the download URL to
work. The loader verifies it received parquet (not a Drive HTML page) before
using a download.

## Deploy

Deployed on [Streamlit Community Cloud](https://share.streamlit.io), pointed at
this repo's `main` branch with `app.py` as the entry point. Pushing to GitHub
redeploys automatically:

```bash
git push origin main
```

No secrets needed — the IDs in `gdrive_manifest.json` are all the app requires,
and the files are shared as "Anyone with the link." To point a deployment at a
different source, set `CASH_DATA_SOURCE` / `CASH_DATA_DIR` in the app's
Settings → Secrets.
## Layout

```
app.py                     entry point: sidebar, data load, view routing
lib/data.py                the loader (see above)
lib/style.py               NMPED palette, masthead, metric cards, formatters
views/*.py                 one file per view, each exposes render(ctx)
sample_data/make_sample.py fabricates cash_data/ so the app runs anywhere
gdrive_manifest.json       table -> Drive file ID
.streamlit/config.toml     theme (shared with the other SBB apps)
assets/nmped_logo.jpg      optional; sidebar logo appears if present
```

## Adding a column to a view

`lib/data.py` selects columns on read (`COLS`) because `cash_lines` is ~1.7M
rows and loading every column costs over a gigabyte. If a view needs a column
that is not there, add it to `COLS` -- never rename one; the names are the
extractor's contract.