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

`agir-cv scinet-transfer` reads your latest query and pulls the matching files (crop, cutout, mask and metadata) from Juno to Ceres or Atlas with Globus.

**One-time setup**

1. Install the Globus CLI and log in:

   ```bash
   uv tool install globus-cli     # if `globus` is not found afterwards: uv tool update-shell
   globus login
   globus session update --all
   ```

2. Fill in the endpoint IDs in `src/agir_cvtoolkit/conf/globus/default.yaml`: `juno_endpoint`, and `endpoint` under `destinations.ceres` (and `atlas` if you use it). They are blank in the repository. The same file sets the destination folders.

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
Files would land in: /90daydata/dash_agir/tmp/semifield-cutouts/NC_2023-07-11/  (on ceres)
Globus link to that folder: https://app.globus.org/file-manager?origin_id=...&origin_path=...
```

Each file keeps its path from the database under the destination's root, so a query spanning several batches lands in `.../semifield-cutouts/` with one subfolder per batch, and a single-batch query lands directly in that batch's folder.

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
