# Demo Checklist

Run this 10 minutes before presenting.

## App Access

- [ ] Databricks App sharing allows the demo users to open the app.
- [ ] The app loads after a hard refresh.
- [ ] The top-right source is `databricks_virtue_foundation_dataset_dais_2026`.
- [ ] The app says `Live data`.
- [ ] No persistent `Warming cache` badge.

## Data State

- [ ] Current dataset count is around `10,000`, not `3`.
- [ ] Dataset preview has more than the tiny local fallback sample available.
- [ ] KPI cards are clickable.
- [ ] Top-level tabs have notification badges.

## Import + Pipeline

- [ ] `demo/data_readiness_demo_import.xlsx` exists.
- [ ] Upload preview parses the workbook.
- [ ] **Run analysis** completes or an existing completed run is visible.
- [ ] Agent cards show the ingestion-led workflow:
  - [ ] Ingest
  - [ ] QA profile
  - [ ] De-dup
  - [ ] Evidence
  - [ ] Geo filter
  - [ ] Shortage
  - [ ] Review gate
  - [ ] Risk synthesis

## Actions

- [ ] Actions queue has visible work.
- [ ] Selecting an action shows evidence and next step.
- [ ] Comment/tag box is editable.
- [ ] Decision buttons are enabled for the selected action.

## Risk

- [ ] Risk recommendations tab has rows.
- [ ] Selecting a risk shows recommendation detail.
- [ ] Risk detail links back to cleanup/actions or evidence review.

## Emergency Debug URLs

Open these from an authenticated Databricks browser session:

```text
/api/status
/api/config
/api/state
/api/diagnostics
```
