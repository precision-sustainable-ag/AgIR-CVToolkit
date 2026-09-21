---
layout: default
title: Installation & Setup
parent: Access & Query
nav_order: 1
---

# Installation & Setup
{: .no_toc }

Install the AgIR-CVToolkit and point it at the database.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| **Python** | 3.13 (uv installs it for you) |
| **OS** | Linux, macOS, or Windows with WSL2 |
| **RAM** | 8 GB minimum; more for large exports |
| **Storage** | About {{ site.data.db_stats.database.size_gb }} GB for the database, plus space for outputs |

---

## Install

The toolkit uses [uv](https://docs.astral.sh/uv/) to manage its environment.

```bash
# Install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Get the toolkit and install it
git clone https://github.com/precision-sustainable-ag/AgIR-CVToolkit.git
cd AgIR-CVToolkit
uv sync

# Check it works
uv run agir-cv --help
```

`uv sync` creates a `.venv` folder with Python 3.13 and installs everything the toolkit needs. The `--help` output lists two commands: `query` and `scinet-transfer`.

{: .note }
> Run commands with `uv run agir-cv ...`, or activate the environment once (`source .venv/bin/activate`) and use `agir-cv ...` directly. The rest of these docs write `agir-cv ...`.

---

## Point the Toolkit at the Database

The database is a single SQLite file (`AgIR_DB_v2_0_202609.db`). To get it on SciNet, see [SciNet Setup](scinet-usage.html#1-get-the-database). Then tell the toolkit where it is, in one of two ways.

**Option 1: config file** (permanent). Edit `semif.db_path` in `src/agir_cvtoolkit/conf/db/default.yaml`:

```yaml
semif:
  db_path: /path/to/AgIR_DB_v2_0_202609.db
  table: semif
```

Leave the other entries in the file as they are.

**Option 2: command-line override** (one-off):

```bash
agir-cv query --db semif -o "db.semif.db_path=/path/to/AgIR_DB_v2_0_202609.db" --preview 5 --limit 5
```

---

## Verify

```bash
agir-cv query --db semif --preview 5 --limit 5
```

You should see five records:

```
============================================================
Preview: First 5 records
============================================================

Record 1:
  ID: MD_Row-15_1656091550
  Image: ...oped-images/MD_2022-06-24/images/MD_Row-15_1656091550.jpg
  Mask: ...-06-24/meta_masks/semantic_masks/MD_Row-15_1656091550.png
  state: MD
  datetime: 2022:06:25 01:23:00
  batch_id: MD_2022-06-24
  image_id: MD_Row-15_1656091550
  season: summer_weeds_2022
  bbot_version: 2.0
  crs: LOCAL
  ... and 7 more fields
------------------------------------------------------------
Record 2:
  ...
```

{: .warning }
> Keep `--limit`. `--preview 5` on its own prints 5 records **and then exports every row in the database**.

The first query on a large file can take a few seconds while it loads.

---

## Output

Each run writes to a standard folder:

```
outputs/runs/{project_name}/{subname}/
├── query/
│   ├── query.csv          # or query.json / query.parquet, per --out
│   └── query_spec.json    # the exact query, for reproducibility
├── cfg.yaml               # configuration snapshot
└── logs/
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `agir-cv: command not found` | Use `uv run agir-cv ...`, or activate the environment with `source .venv/bin/activate`. |
| `FileNotFoundError: Database not found` | Check the path (`ls -lh /path/to/AgIR_DB_v2_0_202609.db`) and use an absolute path. |
| A query runs for a very long time | You left off `--limit`, so it is exporting every match. Press `Ctrl+C` and add `--limit` or a sample. See the [Query Guide](query-tools.html#before-you-run-a-query). |

---

## Update

```bash
git pull
uv sync
```

To uninstall, delete the `.venv` folder.

---

## Next Steps

1. **[SciNet Setup](scinet-usage.html)**: copy the database and transfer files
2. **[Query Guide](query-tools.html)**: filter, sample and export
3. **[SemiF Schema](../dataset/semif.html)**: every column explained
