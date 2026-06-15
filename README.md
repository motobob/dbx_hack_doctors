# dbx_hack_doctors

DBX 2026 hackathon workspace tooling.

This repo is configured for local exploration of this Databricks workspace:

- Workspace ID: `7474647758171864`
- Cloud/region: `aws:us-west-2`
- Workspace UUID: `22b8448d-6839-4df9-9ec6-99001c769190`
- Workspace host: `https://dbc-46f0fbb0-0c1c.cloud.databricks.com`
- Local profile name: `dbx_hack_doctors`
- Catalog: `databricks_virtue_foundation_dataset_dais_2026`
- Schema: `virtue_foundation_dataset`
- Example table: `nfhs_5_district_health_indicators`

If your Databricks browser URL changes, put the current browser URL in `.env`.

## Setup

Install the local Python dependency:

```bash
uv sync
```

Create local environment config:

```bash
cp .env.example .env
```

Preferred auth is Databricks OAuth with the Databricks CLI:

```bash
databricks auth login \
  --host https://dbc-46f0fbb0-0c1c.cloud.databricks.com \
  --profile dbx_hack_doctors
```

If the CLI is not installed yet:

```bash
brew install databricks
```

Personal access token auth also works. Add `DATABRICKS_TOKEN` to `.env`, then run scripts with `--use-env-auth`.

## Explore

OAuth/profile auth:

```bash
uv run python scripts/explore_workspace.py
```

Token/env auth:

```bash
uv run python scripts/explore_workspace.py --use-env-auth
```

The explorer prints the signed-in user plus visible clusters, SQL warehouses, jobs, Unity Catalog catalogs, and workspace root objects. Some sections may be unavailable depending on your Databricks permissions.

Explore the Marketplace catalog/schema metadata:

```bash
uv run python scripts/explore_catalog.py
```

That script lists the visible tables in `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset` and describes the configured table columns. Change `DATABRICKS_TABLE` in `.env` to inspect one of the other tables.

## Download Raw Data

Download every visible table in the Marketplace schema:

```bash
uv run python scripts/download_catalog.py --overwrite
```

Files are written under:

```text
data/raw/databricks_virtue_foundation_dataset_dais_2026/virtue_foundation_dataset/
```

Each table gets a compressed CSV plus `schema.json`. A schema-level `manifest.json` records the downloaded files and row counts.

Inspect the local raw files without querying Databricks:

```bash
uv run python scripts/inspect_local_data.py
```
