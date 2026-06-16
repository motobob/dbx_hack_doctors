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
- **Geographic Score Heatmap** appears above **Mission Control**.
- **Row Uncertainty Distribution** appears next to **Mission Control**.
- **Import + Pipeline** opens.
- `demo/data_readiness_demo_import.xlsx` is available.
- A recent pipeline has completed, or the local pipeline can complete quickly.
- **Actions** has review items.
- **Risk Recommendations** has rows.

If Databricks is unavailable, say "This is the offline/local mode against the checked-in dataset; the same app is designed to use Unity Catalog for source/result/audit state."

## Timed Script

### 0:00-0:15 - Hook and Nonprofit Problem

Click: **Current State**

Say:

> The Virtue Foundation's question sounds simple: where are people underserved, and where should scarce medical resources go next?
> But if facility data is duplicated, weakly located, or over-claims services, a medical desert map can create false confidence at scale.

Fast line:

> Our team cleans healthcare data first, so planning is safer second.

Point to:

- facility count
- data consistency/readiness score
- review queue count
- Geographic Score Heatmap

### 0:15-0:45 - What Was Wrong With The Data

Point to: **Geographic Score Heatmap** and **Row Uncertainty Distribution**

Say:

> The Virtue Foundation dataset gives us more than ten thousand facility records across India. Useful, but not planning-ready.
> We found duplicate names, sparse locations, ambiguous PIN codes, hundreds of state-name variations, invalid fields, weak clinical claims, and conflicting specialties, equipment, procedures, and descriptions.

Click a C or D tier in the heatmap legend, then point to **Dataset Preview**.

Say:

> So the first screen is a trust map, not a completeness dashboard. The point is simple: can this row be trusted enough to count in planning?

Fast line:

> A row full of data can still be unsafe for planning.

### 0:45-1:20 - Data Operations As Specialized Databricks Agents

Click: **Import + Pipeline**

Say:

> Now we run the readiness pipeline against the current facility dataset. The same issues we saw on the map become data operations: schema alignment, QA profiling, dedupe, evidence checks, geography checks, review routing, and risk synthesis.

Click: **Run analysis**, or point to the latest completed run.

Say:

> We packaged those operations as ten specialized Databricks agents. I will not read every agent name here; the important point is that each card owns one step in the trust workflow.

Point to the pipeline cards.

Say:

> The agents do not silently rewrite reality. Safe fixes can apply; ambiguous duplicates, weak claims, suspicious geography, and planning-critical changes escalate.

Fast line:

> The output is not just cleaned data. It is reviewable trust.

### 1:20-1:40 - Extremely Concise Architecture

Stay on: **Import + Pipeline** pipeline panel

Say:

> Architecturally, this is a Databricks App: React, FastAPI, Unity Catalog for governed state, Databricks SQL for access, and Databricks Jobs for the agent pipeline.
> The key is separation: raw source data, working agent findings, and the trusted resulting state planners can use.

Fast line:

> That keeps planners from treating raw scraped records as truth.

### 1:40-2:20 - Human Review And Suggested Reconciliation

Click: **Actions**

Select a strong human-review item, ideally:

- duplicate cluster
- location cleanup
- weak capability claim
- NICU or emergency evidence review

Say:

> This is Data Readiness Desk in action. The agent found a record that should not flow straight into planning.
> For a duplicate cluster, the reconciliation is to preserve the best canonical row, merge only stronger fields, and keep a reviewer note. For a weak capability claim, confirm evidence before it counts toward coverage.

Point to:

- priority
- owner
- confidence
- evidence
- proposed result or next step
- decision note box

Add or reference a note:

```text
Demo review: evidence checked; route for steward confirmation. #demo
```

Click one decision:

- **Needs review**
- **Needs more evidence**
- **Approve**
- **Reject**

Say:

> The decision becomes part of the resulting state and audit trail.

### 2:20-2:50 - Data Readiness Desk Enables Medical Desert Planner

Click: **Risk Recommendations**

Say:

> Medical Desert Planner is downstream from readiness. It asks where trusted evidence exists, where evidence is weak, and where sparse or duplicated data may create false confidence.

Click a risk row.

Point to:

- **Selected Recommendation**
- **Next step**
- **Facts to verify**
- linked cleanup action cards
- **Open cleanup actions**
- **Open evidence queue**
- **Open dedupe queue**

Say:

> Each recommendation has facts to verify, a next step, and links back to cleanup work. Planners and stewards share the same trusted state.

Fast line:

> Data Readiness Desk is the control plane. Medical Desert Planner is the outcome it makes safer.

### 2:50-3:00 - Close

Say:

> The loop is simple: agents triage messy healthcare data, humans proof the decisions that matter, and Databricks turns approved results into a planning-ready trust layer.
> Clean healthcare data first. Plan medical desert outreach second.

## What To Skip If Time Is Tight

- Do not read the full agent list.
- Do not explain every score formula.
- Do not over-explain the heatmap projection; use it as the visual proof that trust has geography.
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
- "A row full of data can still be unsafe."
- "We score trust, not just completeness."
- "Agents do the first pass; humans proof the calls that change planning."
- "Risk is computed from trusted resulting state, not raw scraped claims."
