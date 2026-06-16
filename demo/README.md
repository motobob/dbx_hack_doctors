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
2. The app first shows the Geographic Score Heatmap so trust and uncertainty are visible on the map.
3. Map dots can open facility pills that connect row uncertainty to cleanup actions and risk recommendations.
4. Mission Control and Row Uncertainty Distribution connect the roll-up score to A/B/C/D facility tiers.
5. A new XLSX import enters the pipeline.
6. Databricks agents profile, dedupe, extract evidence, check geography, and open a proof/reject queue.
7. Humans approve only the material uncertain decisions.
8. The trusted resulting state powers actionable risk recommendations with facts, next steps, and links back to cleanup work.

V2 handoff line to keep consistent:

> Ten agents produce a facility trust layer. `row_scorer_v2` scores trust, not just completeness.

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
- Geographic Score Heatmap renders before Mission Control, maps up to 10,000 valid India lat/lon rows, includes zoom controls for dense clusters, its tier legend filters Dataset Preview, and dots open facility pills with action/risk links
- Dataset Preview can filter by row uncertainty tier and state
- Row Uncertainty Distribution replaces the old generic queue card
- Risk Recommendations show a selected recommendation with next step, facts to verify, linked cleanup action cards, and planner note
- no `Warming cache` badge after the first warmup

Reference doc:

- `../docs/agent_workflow_pipeline_v2_lindsay_handoff.md`

If the app shows `unknown_catalog`, only 3 preview rows, or `Warming cache`, stop and validate `/api/status`, `/api/config`, `/api/state`, and `/api/diagnostics` from an authenticated Databricks browser session.
