# Three-Minute Demo Script

## Before You Start

Use the deployed Databricks App if available. The app should be warm and showing live Unity Catalog data.

Expected first-screen signals:

- source catalog: `databricks_virtue_foundation_dataset_dais_2026`
- data state: `Live data`
- facility count: around `10,000`
- no persistent `Warming cache`

If the page shows `unknown_catalog` or only 3 preview rows, use the fallback notes at the bottom.

## Timed Script

### 0:00-0:20 - Open The Story

Click: **Current State**

Say:

> We are solving Track 4, Data Readiness Desk, with Track 2 in mind. The idea is that medical desert planning is only useful if the facility data underneath it can be trusted.

Point to:

- dataset source in the top right
- live data state
- current readiness KPI cards
- top tab notification badges

### 0:20-0:45 - Show The Current Dataset

Say:

> This is the current live dataset from Unity Catalog. We start by showing current consistency, duplicate pressure, human-review volume, and the active drivers that are lowering planning confidence.

Click:

- a top KPI card or notification badge if it has a count

Say:

> These numbers are not decorative. They route the planner toward the action queue that explains what needs to be fixed.

### 0:45-1:15 - Import New Messy Data

Click: **Import + Pipeline**

Upload:

```text
demo/data_readiness_demo_import.xlsx
```

Say:

> Now we drop in more data. This workbook has 12 demo records with exact duplicates, near duplicates, sparse locations, weak capability claims, and suspicious metadata.

Click:

- **Run analysis**

Say:

> Instead of sending this to a human spreadsheet cleanup loop, the Databricks agent workflow takes the first pass.

### 1:15-1:45 - Explain The Agents

Point to pipeline cards.

Say:

> The workflow is ingestion-led. It profiles row quality, detects duplicates, extracts capability evidence, checks geography, estimates shortage signals, and then opens a review gate for the decisions that materially affect planning.

Optional geography line:

> For PIN codes, we are careful: a PIN code is not a district key. The app uses a one-row-per-PIN lookup with confidence and ambiguity flags so facility rows do not fan out or get assigned to the wrong district silently.

Call out expected stages:

- Ingest
- QA profile
- De-dup
- Evidence
- Geo filter
- Shortage
- Review gate
- Risk synthesis

Say:

> The important bit is that the agents do not hide uncertainty. They turn uncertainty into a review item.

### 1:45-2:25 - Work The Actions Queue

Click: **Actions**

Say:

> This is the operational proof/reject queue. Every item has a priority, owner, confidence, lift, evidence, and a next step.

Click:

- the duplicate cluster action

Say:

> For example, this duplicate cluster affects facility counts. If we over-count facilities, we overstate coverage. That is why this lands in the human queue.

Type into the comment box:

```text
Demo review: duplicate evidence checked; route for steward confirmation. #dedupe
```

Click:

- **Needs more evidence** or **Send to review**

Say:

> The reviewer decision becomes part of the resulting state, not a side note in a spreadsheet.

### 2:25-2:50 - Show Risk Recommendations

Click: **Risk Recommendations**

Say:

> The risk planner is downstream from the cleanup. It does not just ask where facilities exist. It asks where trusted evidence exists, where it is weak, and where sparse data may be creating false confidence.

Click:

- a risk row
- **Open cleanup actions** or **Review evidence queue** if visible

Say:

> Risk recommendations link back to the cleanup work, so planners can see whether a care gap is real or whether the data still needs validation.

### 2:50-3:00 - Close

Say:

> That is the end-to-end loop: agents clean and triage the messy dataset, humans proof the risky calls, and the trusted state powers medical desert planning.

## Fallback Notes

If upload parsing fails:

- stay on **Import + Pipeline**
- click **Run analysis**
- explain that the demo file is represented by the current staged pipeline state

If the deployed app shows fallback data:

- say: "This is the local/fallback state, not the live Unity Catalog state."
- open `/api/status`, `/api/config`, `/api/state`, and `/api/diagnostics`
- verify SQL warehouse access, app sharing, Unity Catalog grants, and `DATABRICKS_SQL_USE_CLOUD_FETCH=false`

If the pipeline is still running:

- use the latest completed run shown in the header
- continue to **Actions** and **Risk Recommendations**

## Judge One-Liners

- "Track 4 is the product; Track 2 is the outcome."
- "The system never turns weak evidence into fake certainty."
- "Agents do the cleanup pass; humans proof the decisions that change planning."
- "Risk is computed from the resulting trusted state, not from raw scraped claims."
