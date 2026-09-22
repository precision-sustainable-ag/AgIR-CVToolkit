---
layout: default
title: Scinet Setup
parent: Access & Query
nav_order: 2
---

# SciNet Setup & Usage
{: .no_toc }

Get the database on SciNet, query it, and pull the matching files from Juno.
{: .fs-6 .fw-300 }

---

## Overview

The AgIR database and its cutout files live on **Juno LTS**. On SciNet you will:

1. [Install the toolkit](installation.html)
2. Get the database (section 1 below)
3. Query it (see the [Query Guide](query-tools.html))
4. Transfer the files for your query with Globus (section 2 below)

{: .tip }
> uv keeps its download cache in `~/.cache/uv`, and home quotas on SciNet are small. Before running `uv sync`, set `export UV_CACHE_DIR=/project/<your_project>/uv-cache`.

---

## 1. Get the Database

{: .tip }
> If you are in the `dash_agir` project on Ceres, the database is already at `/project/dash_agir/semifield-database/AgIR_DB_v2_0_202609.db`. Point the toolkit at it (see [Installation](installation.html#point-the-toolkit-at-the-database)) and skip the copy.

Otherwise, copy it from Juno LTS. It is in `/LTS/project/dash_agir/semifield-database/`, and the file is about {{ site.data.db_stats.database.size_gb }} GB.

**Option A: Globus web UI** (easiest)

1. Open [app.globus.org](https://app.globus.org) and log in with your SciNet credentials
2. **Left pane**: select `SCINet-Juno` and go to `/LTS/project/dash_agir/semifield-database/`
3. **Right pane**: select `SCINet-Ceres` and go to `/project/<your_project>/semifield-db/`
4. Select `AgIR_DB_v2_0_202609.db` and click **Start**

**Option B: Globus CLI**

```bash
globus transfer \
  <JUNO_ENDPOINT>:/LTS/project/dash_agir/semifield-database/AgIR_DB_v2_0_202609.db \
  <CERES_ENDPOINT>:/project/<your_project>/semifield-db/AgIR_DB_v2_0_202609.db
```

{: .note }
> Copy to your **project directory**, not your home directory.

Then set `db_path` as described in [Installation](installation.html#point-the-toolkit-at-the-database) and run a query, for example:

```bash
agir-cv query --db semif --preview 5 --limit 5
```

---

## 2. Transfer the Files

`agir-cv scinet-transfer` reads your latest query and pulls the matching files (crop, cutout, mask and metadata) from Juno to Ceres or Atlas with Globus. The examples below follow one query end to end — big primary soybean cutouts:

```bash
agir-cv query --db semif \
  --filters "category_usda_symbol=GLMA4" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --filters "estimated_area_bin=1000-5000,5000-10000,10000+" \
  --limit 100
```

**One-time setup**

1. Install the Globus CLI and log in:

   ```bash
   uv tool install globus-cli     # if `globus` is not found afterwards: uv tool update-shell
   globus login
   globus session update --all
   ```

2. Fill in the endpoint IDs in `src/agir_cvtoolkit/conf/globus/default.yaml`: `juno_endpoint`, and `endpoint` under `destinations.ceres` (and `atlas` if you use it). They are blank in the repository. The same file sets the destination folders.

3. If you also want the run folder copied alongside the files (see [Where files land](#where-files-land) below), set `local_endpoint` in the same file to the endpoint for wherever you run `agir-cv` (usually `SCINet-Ceres`, the same ID as `destinations.ceres.endpoint`). Leave it blank to skip that copy; the file transfer itself does not need it.

**Transfer**

```bash
# Dry run: lists the files and where they would land, submits nothing
agir-cv scinet-transfer

# Start the transfer to Ceres (the default destination)
agir-cv scinet-transfer --submit

# Send to Atlas instead
agir-cv scinet-transfer --dst atlas --submit
```

Both the dry run and `--submit` print the destination folder the files land in (or would land in), and a Globus link that opens that folder for the destination you picked:

```
Files would land in: /90daydata/dash_agir/tmp/demo/big-soy/semifield-cutouts/  (on ceres)
Globus link to that folder: https://app.globus.org/file-manager?origin_id=...&origin_path=...
```

### Where files land

The destination folder for each named destination (`ceres`, `atlas`, ...) is a **shared root** — everyone's transfers use the same `dst_root` in `conf/globus/default.yaml`. To keep them apart, `agir-cv` namespaces it by your run's `project.name` and `project.subname` (the same values behind the local `outputs/runs/<project.name>/<project.subname>/` folder):

```
<dst_root>/<project.name>/<project.subname>/semifield-cutouts/<batch_id>/<file>
```

`project.name` and `project.subname` default to `demo` and `big-soy` (see `conf/config.yaml`), so the query above lands at `.../demo/big-soy/semifield-cutouts/...` with no extra flags. Set your own with `-o project.name=... -o project.subname=...`.

That query touches 5 batches (it has no `batch_id` filter), so it lands directly under `semifield-cutouts/`, with one subfolder per batch. A narrower query — one `batch_id`, or a species that only appears in a single batch — lands one level deeper, directly inside that batch's own subfolder.

**The run folder comes along too.** If `globus.local_endpoint` is set (see step 3 above), `scinet-transfer` also copies this run's local folder — `cfg.yaml`, `logs/`, `query/` (your query results), `globus_batch.txt` and its manifest — into that same project folder, so the destination ends up mirroring your local `outputs/runs/demo/big-soy/` exactly:

```
demo/big-soy/                          # on the destination, under dst_root
├── semifield-cutouts/
│   └── <batch_id>/                    # one subfolder per batch — the actual cutout files
├── cfg.yaml
├── logs/
├── query/
├── globus_batch.txt
└── scinet_transfer_manifest.json
```

This is a second, separate Globus transfer (source: `local_endpoint`, same destination), so it gets its own task ID. Without `local_endpoint` set, `scinet-transfer` says how many run-folder files it would have copied and skips them; the data transfer still runs normally.

{: .tip }
> Add `--filters "cutout_juno_url is not null"` to the query you transfer from. The transfer lists the four file paths of every row, so rows without cutouts would ask for files that do not exist. If a query does return rows with no file paths, `scinet-transfer` says why (for example, that the rows look like zero-detection placeholder rows) instead of transferring nothing silently.

{: .warning }
> Do not use `--projection` on the query you transfer from. The transfer reads the path columns (`cropout_path`, `cutout_path`, `cutout_mask_path`, `cutout_json_path`), and a query without them transfers **0 files**. If you do use `--projection`, include those four columns.

{: .note }
> The transfer reads whichever of `outputs/runs/<project>/<subname>/query/query.json` and `query.csv` was written most recently, so an older file left over from a previous query never shadows your latest one.

To fetch just a few files yourself, each row also has direct download links in `cutout_juno_url` and its sibling columns.

---

## Support

- **SciNet documentation**: [scinet.usda.gov/guides](https://scinet.usda.gov/guides/)
- **AgIR Toolkit issues**: [GitHub Issues](https://github.com/precision-sustainable-ag/AgIR-CVToolkit/issues)
