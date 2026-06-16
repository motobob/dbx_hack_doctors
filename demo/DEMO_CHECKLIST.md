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
- [ ] **Geographic Score Heatmap** appears above **Mission Control**.
- [ ] Heatmap shows mapped rows near the 10,000-point cap, C/D row count, clickable A/B/C/D legend, and zoom controls.
- [ ] Clicking a heatmap tier filters **Dataset Preview**, and the preview can also filter by state.
- [ ] Clicking a map dot opens a facility pill with score/tier/reasons and links to Actions or Risk Recommendations when available.
- [ ] **Row Uncertainty Distribution** appears next to **Mission Control**, not a generic queue card.
- [ ] Demo language says "trust model, not completeness model."
- [ ] Presenter can explain `row_scorer_v2` in one sentence: coherent, evidenced, geospatially plausible, non-duplicative, and safe to count.
- [ ] Dataset preview has more than the tiny local fallback sample available.
- [ ] KPI cards are clickable.
- [ ] Top-level tabs have notification badges.

## Import + Pipeline

- [ ] `demo/data_readiness_demo_import.xlsx` exists.
- [ ] Upload preview parses the workbook.
- [ ] **Run analysis** completes or an existing completed run is visible.
- [ ] Agent cards show the ingestion-led workflow:
  - [ ] 01 Ingestion Manager
  - [ ] 02 QA Profile
  - [ ] 03 PIN Code Ingestion
  - [ ] 04 NFHS Survey Ingestion
  - [ ] 05 Deduplication
  - [ ] 06 Evidence / Claim Verification
  - [ ] 07 Geolocation / Coverage
  - [ ] 08 Shortage
  - [ ] 09 Human Review Gate
  - [ ] 10 Risk / Coverage Scoring

## Actions

- [ ] Actions queue has visible work.
- [ ] Selecting an action shows evidence and next step.
- [ ] Comment/tag box is editable.
- [ ] Decision buttons are enabled for the selected action.

## Risk

- [ ] Risk recommendations tab has rows.
- [ ] Selecting a risk shows **Selected Recommendation**, **Next step**, and **Facts to verify**.
- [ ] Risk detail has linked cleanup action cards.
- [ ] Risk detail links back to cleanup/actions, evidence review, and dedupe review.

## Emergency Debug URLs

Open these from an authenticated Databricks browser session:

```text
/api/status
/api/config
/api/state
/api/diagnostics
```
