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

### 0:00-0:15 - Hook

Click: **Current State**

Say:

> We built Timesharerer Doctors for Track 4, Data Readiness Desk. The thesis is simple: medical desert planning is only useful if the facility data underneath it can be trusted.

Fast line:

> This is a trust model, not a completeness model.

Point to:

- facility count
- readiness score
- Geographic Score Heatmap
- review queue count
- tab badges

### 0:15-0:40 - Geographic Trust Map

Point to: **Geographic Score Heatmap**

Say:

> Before we talk about risk, we show where the data itself is trustworthy. This heatmap plots facility rows across India and colors them by row uncertainty tier, so planners can see whether a region has trusted coverage or just noisy records.

Optional phrase from the v2 handoff:

> A row full of data can still be unsafe.

Point to:

- mapped row count
- 10,000-point cap note
- C/D row count
- zoom controls for inspecting dense clusters
- dense clusters of weak or strong records
- clickable tier legend that filters Dataset Preview
- action/risk rings on dots

Fast line:

> The product starts by making uncertainty geographic.

Click a C or D tier legend item, then point to **Dataset Preview**:

> The map is explainable, not decorative. Clicking a tier carries that uncertainty slice down into the underlying rows, and the state filter lets a reviewer isolate the geography behind a cluster.

Click a dot with an action or risk ring:

> Each dot can open the work behind that row. The pill shows the facility, tier, score, reason codes, and links back into cleanup actions or risk recommendations.

### 0:40-1:05 - Mission Control + Row Scores

Point to: **Mission Control** and **Row Uncertainty Distribution**

Say:

> Mission Control gives the roll-up, but the row distribution tells us how many facilities are trusted enough to count. This replaces generic queues with a real trust map: A/B rows can support planning, while C/D rows become proof or steward work.

Fast line:

> row_scorer_v2 asks whether each row is coherent, evidenced, geospatially plausible, non-duplicative, and safe to count.

Click one KPI or CTA that jumps toward **Actions**, then return or continue if the app lands there naturally.

Fast line:

> The product starts by making uncertainty visible.

### 1:05-1:40 - Import + Pipeline

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

Point to agent cards as:

- 01 Ingestion Manager
- 02 QA Profile
- 03 PIN Code Ingestion
- 04 NFHS Survey Ingestion
- 05 Deduplication
- 06 Evidence / Claim Verification
- 07 Geolocation / Coverage
- 08 Shortage
- 09 Human Review Gate
- 10 Risk / Coverage Scoring

If a completed run is already visible:

> This completed run shows all ten agents finished cleanly. The green signal cards are raw agent findings, not the curated action or risk counts.

### 1:40-2:20 - Actions Queue

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

### 2:20-2:50 - Risk Recommendations

Click: **Risk Recommendations**

Say:

> The risk planner is downstream from readiness. It does not just ask where facilities exist. It asks where trusted evidence exists, where evidence is weak, and where sparse data may be creating false confidence.

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

> This is not a passive recommendation table. Each planning signal has facts, a next step, and links back to the cleanup work that must be resolved before anyone treats the gap as real.

Click a linked cleanup action card or **Open cleanup actions** if time allows:

> The risk recommendation stays connected to the proof/reject queue, so planning and data stewardship are part of the same workflow.

### 2:50-3:00 - Close

Say:

> That is the loop: agents triage messy healthcare data, humans proof the decisions that matter, and the trusted resulting state powers medical desert planning.

Optional slogan close:

> Inspire people to go further and share more.

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
