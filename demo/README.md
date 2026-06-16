# Demo Materials

This folder contains the click-through assets for the three-minute Databricks App demo.

## Files

- `DEMO_NARRATIVE.md`: the judging story and product framing.
- `DEMO_SCRIPT.md`: the timed presenter script and click path.
- `DEMO_CHECKLIST.md`: quick pre-demo validation checklist.
- `SCORE_GUIDE.md`: plain-English definitions for every percentage score.
- `DEVPOST_STORY.md`: submission story in the standard Devpost prompt format.
- `data_readiness_demo_import.xlsx`: a 12-row import workbook designed to trigger the pipeline.

## Demo Promise

We are solving **Track 4: Data Readiness Desk** with **Track 2: Medical Desert Planner** as the downstream outcome.

The story is simple:

1. The planner starts with 10,000 messy facility records from Unity Catalog.
2. The app shows current readiness, active issues, and what needs attention.
3. A new XLSX import enters the pipeline.
4. Databricks agents profile, dedupe, extract evidence, check geography, and open a proof/reject queue.
5. Humans approve only the material uncertain decisions.
6. The trusted resulting state powers risk recommendations for medical desert planning.

## Demo Workbook

Use:

```text
demo/data_readiness_demo_import.xlsx
```

The workbook intentionally includes:

- exact duplicates
- near duplicates
- sparse location fields
- weak NICU, emergency, trauma, maternity, and oncology claims
- suspicious metadata
- records that should route to human review

## DBX Demo Rule

For the real deployed demo, the app should show live Unity Catalog data, not fallback data.

Expected signals:

- source catalog is `databricks_virtue_foundation_dataset_dais_2026`
- state says `Live data`
- current dataset count is around `10,000`
- no `Warming cache` badge after the first warmup

If the app shows `unknown_catalog`, only 3 preview rows, or `Warming cache`, stop and validate `/api/status`, `/api/config`, `/api/state`, and `/api/diagnostics` from an authenticated Databricks browser session.
