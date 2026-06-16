# Three-Minute Demo Script

## Goal

Show one tight loop:

1. raw facility data is not planning-ready
2. agents triage the data-quality problems
3. humans proof/reject the material calls
4. trusted resulting state powers risk recommendations

The demo is three minutes. Do not explain every agent. Show the loop.

## Before You Start

Preferred path:

- Run the deployed Databricks App if it is warm and showing live data.
- Otherwise run local/offline mode:

```bash
./run.sh dev local
```

Open the app and pre-check:

- **Current State** loads.
- **Import + Pipeline** opens.
- `demo/data_readiness_demo_import.xlsx` is available.
- A recent pipeline has completed, or the local pipeline can complete quickly.
- **Actions** has review items.
- **Risk Recommendations** has rows.

If Databricks is unavailable, say "This is the offline/local mode against the checked-in dataset; the same app is designed to use Unity Catalog for source/result/audit state."

## Timed Script

### 0:00-0:15 - Hook

Click: **Current State**

Say:

> We built Timesharerer Doctors for Track 4, Data Readiness Desk. The thesis is simple: medical desert planning is only useful if the facility data underneath it can be trusted.

Point to:

- facility count
- readiness score
- review queue count
- tab badges

### 0:15-0:40 - Current State

Say:

> This is the current facility dataset. The app shows duplicate pressure, sparse locations, weak evidence, and the review work that could change planning confidence. These cards are not decorative; they route directly into cleanup work.

Click one KPI or CTA that jumps toward **Actions**, then return or continue if the app lands there naturally.

Fast line:

> The product starts by making uncertainty visible.

### 0:40-1:15 - Import + Pipeline

Click: **Import + Pipeline**

Upload or point to:

```text
demo/data_readiness_demo_import.xlsx
```

Say:

> Now we stage a messy incoming file. This demo workbook has exact duplicates, near duplicates, sparse locations, weak clinical claims, and suspicious metadata.

Point to:

- horizontal import bar
- scratchpad on the left
- AI Pipeline on the right

Click:

- **Run ingestion** if an upload preview is ready
- otherwise **Run analysis**

Say:

> The pipeline does the first pass: ingest, QA, PIN and NFHS context, dedupe, evidence, geography, shortage, review gate, and risk synthesis.

If a completed run is already visible:

> This completed run shows all ten agents finished cleanly. The green notifications are review work, not failed tasks.

### 1:15-2:05 - Actions Queue

Click: **Actions**

Say:

> This is the proof/reject queue. Each item has priority, owner, confidence, evidence, and a next step. The agents do not hide uncertainty; they turn it into work.

Click a high-signal item, preferably:

- duplicate cluster
- location quality
- capability evidence
- NICU review

Say:

> If we over-count duplicate facilities, we overstate coverage. If we trust a weak capability claim, we may send planners toward the wrong care gap. That is why material decisions land here.

Add note:

```text
Demo review: evidence checked; route for steward confirmation. #demo
```

Click one decision:

- **Needs review**
- **Needs more evidence**
- **Send to review**
- or **Approve** if the item is clearly safe

Say:

> The reviewer decision becomes part of the resulting state instead of living in a side spreadsheet.

### 2:05-2:45 - Risk Recommendations

Click: **Risk Recommendations**

Say:

> The risk planner is downstream from readiness. It does not just ask where facilities exist. It asks where trusted evidence exists, where evidence is weak, and where sparse data may be creating false confidence.

Click a risk row.

If visible, click or point to:

- **Open cleanup actions**
- **Open evidence queue**

Say:

> Planning recommendations link back to cleanup actions, so the team can tell whether a care gap is real or whether the data still needs validation.

### 2:45-3:00 - Close

Say:

> That is the loop: agents triage messy healthcare data, humans proof the decisions that matter, and the trusted resulting state powers medical desert planning.

## What To Skip If Time Is Tight

- Do not read the full agent list.
- Do not explain every score formula.
- Do not scroll deeply through the dataset preview.
- Do not wait for a long cloud run; use the latest completed run.
- Do not open diagnostics unless the app is failing.

## Fallbacks

If upload parsing fails:

- stay on **Import + Pipeline**
- click **Run analysis**
- say the demo file is represented by the current staged/local pipeline state

If the pipeline is still running:

- say "The run is asynchronous; for the judging walkthrough, I will use the latest completed run."
- continue to **Actions**

If Databricks is down:

- run `./run.sh dev local`
- say "This is local/offline mode with checked-in data and deterministic agents; Unity Catalog persistence is the cloud target."

If the app shows fallback data:

- say "This is fallback/local state, not live Unity Catalog."
- do not claim live DBX data

## Judge One-Liners

- "Track 4 is the product; Track 2 is the outcome."
- "The app never turns weak evidence into fake certainty."
- "Agents do the first pass; humans proof the calls that change planning."
- "Risk is computed from trusted resulting state, not raw scraped claims."
