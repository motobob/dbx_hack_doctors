# Data Readiness Desk Build Plan

## One-line Story

Build a Databricks App for non-technical healthcare planners that turns 10,000 messy India healthcare facility records into a trusted action queue, then rolls those fixes into risk-aware planning recommendations for medical deserts.

Primary challenge track: **Track 4 - Data Readiness Desk**

Downstream outcome: **Track 2 - Medical Desert Planner**

## Problem We Are Solving

The source dataset has useful facility information, but it is not clean enough to trust for planning. Facility names may be duplicated, locations may be sparse or inconsistent, descriptions may contain uneven claims, and claimed capabilities may contradict structured fields.

The app answers:

- What is wrong with this dataset?
- Which records should a human review first?
- Which issues can an AI agent fix automatically?
- How much did data readiness improve after deduplication and cleanup?
- Where might planners still have high-risk care gaps after accounting for messy data?

## Target Users

- NGO coordinators deciding where to send field teams.
- Healthcare planners evaluating service coverage by geography.
- Analysts who need evidence without writing SQL.
- Data stewards who need a review queue instead of a raw spreadsheet.

## Product Promise

"Drop in messy facility data. Get a measurable trust score, a prioritized cleanup queue, evidence for every recommendation, and a planning-ready view of high-risk locations and doctors."

## Demo Flow

1. **Open Dashboard**
   - Show the current dataset readiness KPI.
   - Example headline: `Current data consistency: 62%`
   - Show estimated improvement after recommended fixes.
   - Example headline: `Expected improvement after dedupe and high-confidence fixes: +18%`

2. **Import More Data**
   - User uploads XLS/XLSX/CSV facility files.
   - App validates columns, previews rows, and maps uploaded fields into the canonical facility schema.
   - Uploaded records are staged, profiled, and compared against existing records before merge.

3. **Profile and Deduplicate**
   - Detect exact duplicates.
   - Detect fuzzy duplicates across facility name, city, district, PIN code, address, phone, and specialties.
   - Group likely duplicate clusters.
   - Recommend merge actions with confidence and evidence.

4. **Review Recommendations and Actions**
   - Surface sparse fields, missing location data, suspicious claims, contradictions, and inconsistent specialties.
   - Split recommendations into:
     - `Auto-fix candidates`
     - `Needs human confirmation`
     - `Planning risk warnings`

5. **Act on Recommendations**
   - User approves, edits, rejects, or saves recommendations.
   - AI agent can auto-fix high-confidence issues such as canonical names, whitespace cleanup, obvious duplicate merges, normalized specialties, and standardized location labels.
   - Ambiguous issues stay in the human review queue.

6. **Show Planning Outcome**
   - App translates cleaned, trust-weighted data into risk recommendations.
   - Example: "Look at XYZ district and these doctors/facilities because maternity evidence is weak, records are sparse, and nearest trusted alternative is far away."

## UX and UI Mockups

The app should feel like a Databricks-native operational dashboard: dense, calm, evidence-first, and optimized for repeated review work. The MVP should use **three primary tabs** instead of a deep navigation tree:

- `Current Dataset`
- `Import + Actions`
- `Risk Recommendations`

This keeps the hackathon story clean: first show what is wrong with the current dataset, then let the user add data and review fixes, then show what the cleaned evidence means for planning.

Databricks Apps assumptions:

- Build the first version as a Streamlit Databricks App.
- Use Databricks workspace auth instead of a separate login screen.
- Read and write through Unity Catalog tables.
- Keep long-running profiling, dedupe, and AI extraction jobs behind buttons with visible run status.
- Use Databricks SQL or Spark-backed tables for persisted outputs, not only Streamlit session state.
- Make the UI usable in a browser tab embedded in the Databricks workspace.

### Global App Frame

```text
+----------------------------------------------------------------------------------+
| Data Readiness Desk                                   Catalog: dais_2026          |
| Track 4 cleanup -> Track 2 planning                   Last run: 2026-06-15 09:42  |
+----------------------------------------------------------------------------------+
| [Current Dataset] [Import + Actions] [Risk Recommendations]                       |
+----------------------------------------------------------------------------------+
| Page content                                                                      |
+----------------------------------------------------------------------------------+
```

Global controls:

- Catalog/schema selector.
- Dataset/table selector.
- Date or run selector.
- `Run Profile` button.
- `Save Snapshot` button.
- Status pill: `Sample`, `Staged`, `Live`, or `Needs refresh`.

Global design rules:

- Use compact cards only for metrics and repeated row summaries.
- Use full-width tables for review workflows.
- Use status colors sparingly: red for critical, amber for review, green for trusted, gray for unknown.
- Never hide uncertainty; show confidence beside every recommendation.
- Keep every recommendation tied to source evidence.

### Tab 1: Current Dataset Mockup

Purpose: This is the landing page. It shows the current dataset, current numbers, data readiness score, and the highest-level evidence that the dataset needs cleanup before planning.

```text
+----------------------------------------------------------------------------------+
| Current Dataset                                                                  |
| What we know right now about the facility dataset                                 |
+-------------------+-------------------+-------------------+----------------------+
| Consistency Score | Expected Lift     | Duplicate Clusters| Human Review Queue   |
| 62%               | +18 pts           | 428               | 1,284 records        |
| Needs work        | After safe fixes  | 96 high impact    | 312 critical         |
+-------------------+-------------------+-------------------+----------------------+
| Records 10,000    | States 28         | Districts 612     | Sparse Locations 931 |
+-------------------+-------------------+-------------------+----------------------+
| Current Data Stats                                                               |
| Completeness 74% | Dedupe Health 51% | Location Quality 68% | Evidence 55%       |
+----------------------------------------------------------------------------------+
| Top Drivers of Low Trust                                                         |
| [bar] Duplicate records                 31% of penalty                          |
| [bar] Missing PIN/district              22% of penalty                          |
| [bar] Weak capability evidence          19% of penalty                          |
| [bar] Contradictory specialty claims    14% of penalty                          |
+----------------------------------------------------------------------------------+
| Current Dataset Preview                                                          |
| facility_name | district | pin_code | specialties       | readiness_flags        |
| City Care     | Jaipur   | 302001   | ICU, emergency    | possible duplicate     |
| Shree Mat.    | Jaipur   | blank    | maternity         | weak NICU evidence     |
| Apex Hosp.    | Patna    | 800001   | emergency surgery | missing source date    |
+----------------------------------------------------------------------------------+
| Primary actions: [Run Profile] [Import More Data] [Open Recommendations]          |
```

Key interactions:

- Clicking a KPI filters the dataset preview and recommendation list.
- Clicking a driver switches to `Import + Actions` with that issue type selected.
- `Run Profile` recomputes the latest readiness snapshot.
- `Import More Data` switches to the import section in the second tab.

Implementation notes:

- Use `st.metric` for headline KPIs.
- Use `st.progress` for score components.
- Use `st.dataframe` for the current dataset preview.
- Persist KPI snapshots to `readiness_kpi_snapshot`.

### Tab 2: Import + Actions Mockup

Purpose: This is the workbench. It combines XLS/XLSX/CSV import with the list of recommendations and actions found in the data. Dedupe, findings, and human review live here as sections.

```text
+----------------------------------------------------------------------------------+
| Import + Actions                                                                 |
| Add data, validate it, then review the recommended fixes                          |
+----------------------------------------+-----------------------------------------+
| Upload File                            | Import Quality                          |
| [ Drop XLS/XLSX/CSV here           ]   | Parsed rows: 2,140                       |
| Source name: [ district_partner_june ] | Required fields present: 81%             |
| Import mode: [Stage only v]            | Likely duplicates: 187                   |
| [Validate Import] [Stage Records]      | Import readiness: 69%                    |
+----------------------------------------+-----------------------------------------+
| Column Mapping                                                                  |
| Uploaded column        -> Canonical field           Status                       |
| Hospital Name          -> facility_name             ok                           |
| City                   -> city                      ok                           |
| Services               -> description               review                       |
| Contact                -> phone                     ok                           |
| LatLong                -> latitude/longitude         parse needed                 |
+----------------------------------------------------------------------------------+
| Preview and Validation                                                           |
| Row | facility_name | district | pin_code | issue                                |
| 12  | City Care     | blank    | 302001   | Missing district                    |
| 19  | Apex Hosp.    | Jaipur   | 302001   | Possible duplicate                  |
+----------------------------------------------------------------------------------+
+----------------------------------------------------------------------------------+
| Recommendations / Actions Found in the Data                                      |
| Filters: [Priority v] [Owner v] [Issue Type v] [State v] [Confidence v]           |
+----------------------------------------------------------------------------------+
| Priority | Recommendation                         | Owner    | Lift | Status      |
| P0       | Merge 3 City Care duplicate records     | Human    | +3.2 | Needs review|
| P0       | Normalize 412 district spellings         | AI agent | +2.4 | Ready       |
| P1       | Confirm NICU claim at Shree Maternity    | Human    | +1.8 | Open        |
| P1       | Standardize oncology specialty labels    | AI agent | +1.1 | Ready       |
+----------------------------------------------------------------------------------+
| Selected Recommendation Detail                                                    |
| Issue: Merge 3 City Care duplicate records                                        |
| Evidence: same PIN, same phone digits, 0.92 name similarity, shared address tokens|
| AI recommendation: Merge into canonical facility entity                           |
| Human note: [                                                            ]        |
| [Approve] [Reject] [Ask Human] [Apply AI Safe Fixes] [Export Review CSV]          |
+----------------------------------------------------------------------------------+
```

Key interactions:

- User uploads XLS/XLSX/CSV, validates it, and stages records.
- The action table shows all recommendations found in both the current dataset and staged imports.
- Selecting an action opens the evidence/detail panel.
- AI-owned actions can be applied in batch only when confidence is high.
- Human-owned actions require approve/reject/ask-human status changes.
- Every import, action, and decision writes an audit event.

Implementation notes:

- Use `st.file_uploader` with CSV and Excel support.
- Use `pandas.read_csv` and `pandas.read_excel` locally in the app for preview.
- Push staged rows into Unity Catalog only after validation.
- Use `st.tabs` for queue segments.
- Use `st.data_editor` when inline status changes are needed.
- Apply actions through explicit buttons, not automatic table edits.
- Store reviewer notes and status changes.
- Persist action state to `action_recommendations`.

### Tab 3: Risk Recommendations Mockup

Purpose: This is the Track 2 outcome. It uses the cleaned and trust-weighted evidence to recommend locations, doctors, and facilities to investigate.

```text
+----------------------------------------------------------------------------------+
| Risk Recommendations                                                             |
| Where planners should look after accounting for messy data                        |
+--------------------------------------+-------------------------------------------+
| Map / Geography Summary                | Recommendation Detail                     |
| State: Rajasthan                       | Selected: Jaipur district                 |
| Capability: Emergency                  | Risk: Possible emergency coverage gap     |
| Trust mode: Deduped + evidence-weighted| Confidence: Medium                        |
|                                      | Why: 5 claimed emergency facilities,       |
| [district risk table or map]           | but only 2 have strong evidence and one    |
|                                      | duplicate cluster may inflate coverage.    |
+--------------------------------------+-------------------------------------------+
| Locations and Doctors/Facilities to Review                                       |
| Priority | Location/PIN | Facility/Doctor       | Reason                         | Confidence |
| P0       | 302001       | City Care Hospital    | duplicate affects coverage     | High       |
| P1       | 302004       | Shree Maternity       | NICU claim is weak             | Medium     |
| P1       | 302006       | Apex Emergency Centre | sparse description             | Medium     |
+----------------------------------------------------------------------------------+
```

Key interactions:

- User selects geography and care need.
- App shows trust-weighted coverage and uncertainty.
- Recommendations explain whether a gap is likely real or data-poor.
- User can save a planning note or export a risk list.

Implementation notes:

- Use a table-first view for MVP.
- Add maps only if coordinates are reliable.
- If coordinates are sparse, use district/PIN tables instead of pretending precision.
- Persist output to `geo_risk_recommendations`.

## Visual Design Direction

The visual direction should be practical and credible for healthcare data operations.

Layout:

- Three top-level tabs: `Current Dataset`, `Import + Actions`, and `Risk Recommendations`.
- Page title and short context line at top.
- Main filters in a compact horizontal row.
- KPI cards across the top of the landing tab.
- Tables should take most of the width.
- Evidence panels should appear below or beside selected rows.

Palette:

- Background: white or near-white.
- Text: dark neutral.
- Accent: Databricks-style red/orange only for primary actions and selected states.
- Status colors: green, amber, red, gray.
- Avoid a one-color blue or purple analytics theme.

Typography:

- Use Streamlit defaults unless custom CSS is needed.
- Keep headings compact.
- Use short labels in tables and cards.

Component rules:

- Buttons for clear commands: `Run Profile`, `Stage Records`, `Approve Merge`, `Apply AI Safe Fixes`.
- Select boxes for filters and column mapping.
- Tabs for queue states.
- Expanders for evidence and source rows.
- Progress bars for score components.
- Dataframes/editors for work queues.

Empty states:

- No profile run: show `Run Profile` as the primary action.
- No upload staged: show the upload control and expected file types.
- No findings: show that the current filter has no issues, not that the dataset is perfect.
- No risk output: ask the user to select a geography and capability.

Loading states:

- Profile run: `Profiling completeness, duplicates, contradictions, and capability evidence...`
- Dedupe run: `Building candidate clusters and scoring match evidence...`
- AI extraction: `Extracting capability evidence from descriptions...`
- Save: `Writing decisions to Unity Catalog...`

Error states:

- Missing warehouse or permissions: explain which table or operation failed.
- Upload parse error: show filename, row number if available, and expected format.
- Save failure: keep user decisions in session and provide retry.
- Empty source table: ask user to choose another table or upload a file.

## Core Tab Requirements

### 1. Current Dataset

Purpose: The landing tab. Let a planner understand the current dataset before any new import or cleanup.

Widgets:

- Data consistency KPI.
- Estimated KPI lift from recommended fixes.
- Duplicate cluster count.
- High-risk records needing review.
- Sparse geography count.
- Suspicious capability claim count.
- Current dataset stats: records, states, districts, sources, last profile run.
- Dataset preview with readiness flags.

Primary CTA:

- `Open Recommendations`

Secondary CTAs:

- `Run Profile`
- `Import More Data`

### 2. Import + Actions

Purpose: Let users drop more data into the workflow and act on the recommendations found in the current and staged data.

Features:

- XLS/XLSX/CSV upload.
- Column mapping assistant.
- Required field validation.
- Preview of first 100 rows.
- Schema mismatch warnings.
- Staged import table.
- Import quality score before commit.
- Recommendation/action list.
- Dedupe cluster review.
- Evidence drawer for selected action.
- AI safe-fix batch action.
- Human review decisions.
- Export review CSV.
- Audit event capture.

Canonical columns:

- `facility_id`
- `facility_name`
- `address`
- `state`
- `district`
- `city`
- `pin_code`
- `latitude`
- `longitude`
- `phone`
- `specialties`
- `description`
- `claimed_capabilities`
- `source`
- `last_updated`

Candidate matching signals:

- Normalized facility name similarity.
- Same or nearby PIN code.
- Same phone number.
- Same address tokens.
- Same district/city/state.
- Same specialty list.
- Geospatial distance if coordinates exist.

Finding types:

- Duplicate facility.
- Missing or weak location.
- Suspicious capability claim.
- Capability contradiction.
- Sparse description.
- Missing specialty.
- Conflicting specialty.
- Facility type mismatch.
- Outlier location.
- Low evidence for high-impact service.

Each finding includes:

- Severity.
- Confidence.
- Affected field.
- Recommended action.
- Evidence from structured fields and free text.
- Suggested owner: `AI agent` or `Human reviewer`.
- Planning impact.

Action list columns:

- Priority.
- Facility or cluster.
- Issue.
- Recommendation.
- Confidence.
- Evidence.
- Suggested action.
- Owner.
- Status.

Statuses:

- `Open`
- `Auto-fixed`
- `Needs review`
- `Approved`
- `Rejected`
- `Saved for later`

### 3. Risk Recommendations

Purpose: Connect Track 4 cleanup to Track 2 planning.

This screen does not pretend the data is perfect. It shows planning recommendations with uncertainty.

Recommendation examples:

- "XYZ district may be underserved for emergency care because trusted emergency evidence is low and facility descriptions are sparse."
- "Review these doctors/facilities before planning outreach because duplicate clusters may inflate apparent coverage."
- "This PIN code appears data-poor rather than truly underserved; collect more data before making a resource decision."

Signals:

- Trust-weighted facility count by geography.
- Capability evidence strength.
- Duplicate-adjusted coverage.
- Sparse-data penalty.
- Location confidence.
- Distance to nearest trusted facility.
- Human-review backlog in that geography.

## Readiness KPI

The headline KPI should be understandable, measurable, and explainable.

Proposed metric:

```text
data_consistency_score =
  0.25 * completeness_score
+ 0.20 * duplicate_health_score
+ 0.20 * contradiction_score
+ 0.15 * location_quality_score
+ 0.10 * capability_evidence_score
+ 0.10 * provenance_score
```

Where:

- `completeness_score`: required fields present and usable.
- `duplicate_health_score`: records are not likely duplicates.
- `contradiction_score`: structured and text claims do not conflict.
- `location_quality_score`: location fields are specific and valid.
- `capability_evidence_score`: capability claims have supporting evidence.
- `provenance_score`: source and update metadata are available.

Demo phrasing:

```text
Current data consistency: 62%
After recommended dedupe and auto-fixes: 80%
Estimated improvement: +18 points
```

The app should show exactly which fixes contribute to the lift.

## AI Agent Behavior

The AI agent should be useful but cautious.

Auto-fix allowed:

- Normalize whitespace and capitalization.
- Standardize common specialty labels.
- Standardize known state/district names.
- Merge exact duplicates.
- Merge very high-confidence duplicates if evidence is strong.
- Extract claimed capabilities from descriptions with evidence snippets.
- Suggest canonical facility names.

Human confirmation required:

- Ambiguous duplicate merges.
- Contradictory clinical capability claims.
- Records with planning impact above a configured threshold.
- Location changes that move a facility across district/city/PIN.
- Any recommendation with low or medium confidence.

Every AI recommendation must include:

- What changed.
- Why it changed.
- Evidence.
- Confidence.
- Undo path.

## Evidence Model

For each facility and capability, store evidence separately from conclusions.

Suggested capability labels:

- ICU
- NICU
- Emergency
- Maternity
- Trauma
- Oncology
- Dialysis
- Surgery
- Radiology
- Blood bank

Evidence fields:

- `capability`
- `claim_status`: `strong`, `partial`, `weak`, `suspicious`, `none`
- `source_field`
- `evidence_text`
- `confidence`
- `reason`
- `created_at`

This lets the app communicate uncertainty honestly and lets planners inspect why a claim was trusted or flagged.

## Data Architecture

### Bronze Tables

Raw and staged data.

- `raw_facilities`
- `raw_uploaded_files`
- `raw_uploaded_rows`

### Silver Tables

Cleaned and normalized data.

- `facility_records_normalized`
- `facility_duplicate_candidates`
- `facility_entity_clusters`
- `facility_capability_evidence`
- `data_quality_findings`

### Gold Tables

Planner-ready outputs.

- `facility_entities`
- `readiness_kpi_snapshot`
- `action_recommendations`
- `geo_risk_recommendations`

## Suggested Databricks Stack

- Databricks App frontend with Streamlit for the fastest dashboard build.
- Unity Catalog tables for Bronze/Silver/Gold data.
- Databricks SQL for aggregations and KPI queries.
- Spark for dedupe, profiling, and fuzzy matching jobs.
- Mosaic AI / model serving for evidence extraction and recommendation explanations if available.
- MLflow or table-based audit logs for recommendation runs.

## App Skeleton

```text
app/
  app.py
  app.yaml
  requirements.txt
  tabs/
    current_dataset.py
    import_actions.py
    risk_recommendations.py
  lib/
    databricks.py
    kpi.py
    profiling.py
    dedupe.py
    evidence.py
    recommendations.py
    uploads.py
  sql/
    bronze.sql
    silver.sql
    gold.sql
  sample_data/
    facilities_sample.csv
```

## First Build Milestone

Goal: A clickable dashboard that tells the story end to end with real or sample data.

Deliverables:

- Streamlit Databricks App skeleton.
- `Current Dataset` tab with KPI cards, current stats, and dataset preview.
- `Import + Actions` tab with upload control for XLS/XLSX/CSV.
- Mocked or live recommendation/action table.
- `Risk Recommendations` tab with planning-risk table.
- Basic evidence drawer for one selected recommendation.

Acceptance criteria:

- A non-technical user can understand the current data readiness score.
- A user can upload a file and see validation feedback.
- Recommendations and duplicate issues are ranked by priority.
- Recommendations clearly say whether AI can fix them or a human should review.
- Risk recommendations separate real care gaps from data-poor regions.

## Second Build Milestone

Goal: Replace mocked logic with real profiling and dedupe.

Deliverables:

- Read raw dataset from Unity Catalog or downloaded CSVs.
- Normalize facility names, location fields, phones, and specialties.
- Generate duplicate candidates.
- Compute readiness KPI from actual data.
- Generate action recommendations from actual findings.
- Persist user decisions.

Acceptance criteria:

- KPI changes after applying approved fixes.
- Duplicate clusters have explainable evidence.
- Findings are reproducible from source data.
- User approvals are saved.

## Third Build Milestone

Goal: Add AI-assisted evidence extraction and planning recommendations.

Deliverables:

- Extract capability evidence from free-text descriptions.
- Classify claims as strong, partial, weak, suspicious, or none.
- Create geography-level risk recommendations.
- Add uncertainty labels and evidence snippets.
- Add export/save workflow.

Acceptance criteria:

- Capability claims always show evidence.
- Risk recommendations include confidence and uncertainty.
- High-risk geographies account for sparse data and duplicate inflation.
- Saved work can be revisited.

## Demo Script

1. "We start with a messy facility dataset that looks useful but cannot yet be trusted."
2. "The app scores current data consistency at 62% and shows the exact issues pulling it down."
3. "The biggest problem is duplicate and contradictory facility records, so the app creates a prioritized review queue."
4. "High-confidence fixes can be handled by an AI agent, while risky changes ask a human to confirm."
5. "After dedupe and cleanup, consistency improves to 80%, a lift of 18 points."
6. "Now the planner view is more trustworthy: we can see which locations may have real service gaps versus which ones are simply data-poor."
7. "The final output is not just a chart. It is a saved list of recommended fixes and a second list of planning risks to investigate."

## Hackathon Judging Points

Why this fits Track 4:

- Profiles data quality.
- Finds duplicates and contradictions.
- Surfaces sparse fields and suspicious claims.
- Prioritizes high-leverage records for review.
- Lets users save or revise work.

Why this supports Track 2:

- Produces trust-weighted facility evidence.
- Avoids over-counting duplicate facilities.
- Highlights data-poor regions.
- Communicates uncertainty.
- Recommends locations and doctors/facilities to investigate.

Why it is practical:

- Starts with a dashboard a planner can understand.
- Uses Databricks tables as the system of record.
- Separates evidence from conclusions.
- Keeps humans in control for risky changes.

## Open Questions

- What is the actual facility table name in the Marketplace catalog?
- Which fields are present in the 10,000-record facility dataset?
- Are latitude and longitude included, or do we need geocoding?
- Which AI model endpoint is available in the workspace?
- Do we need role-based review permissions for NGO users versus data stewards?
- Should auto-fixes write back to the source table or only to curated Gold tables?

## Immediate Next Steps

1. Explore the Databricks catalog and identify the facility dataset table.
2. Download or query a representative sample.
3. Create the Streamlit app skeleton under `app/`.
4. Implement the KPI calculation on sample data.
5. Implement the first duplicate candidate generator.
6. Build the action queue UI.
7. Add the risk recommendations view using trust-weighted geography aggregates.
