# Agent Specs and State

This folder contains the current Data Readiness Desk agents. They can run in-process through FastAPI or as Databricks multi-task Job tasks.

The architecture was refined in `docs/design-session-2026-06-15-agent-architecture.md`. The current skeleton treats ingestion as a manager/workflow, with QA/Profile, Dedupe, Evidence/Specialty, Geo, Shortage, Human Review, and Risk stages.

## Demo Contract

The agent workflow exists to make the Track 4 story demoable in three minutes while producing the Track 2 side effect:

- Ingest new or updated facility data.
- Find quality, duplicate, evidence, and location problems automatically.
- Produce a proof/reject queue instead of asking users to clean rows manually.
- Commit approved fixes into the trusted resulting state.
- Generate risk-planning recommendations only from that resulting state.

```mermaid
flowchart LR
  raw[Source state] --> ingest[Ingest]
  ingest --> agents[Agent checks and fixes]
  agents --> gate[Human proof / reject]
  gate --> resulting[Resulting state]
  resulting --> risk[Risk planner]
```

## Execution Graph

```mermaid
flowchart LR
  start[POST /api/pipeline/start] --> ingestion[IngestionManagerAgent]
  ingestion --> qa[QAProfileAgent]
  qa --> dedup[DedupAgent]
  qa --> evidence[EvidenceSpecialtyAgent]
  qa --> geo[GeoAgent]
  dedup --> shortage[ShortageAgent]
  evidence --> shortage
  geo --> shortage
  shortage --> review[HumanReviewGateAgent]
  review --> risk[RiskAgent]
  shortage --> risk
  risk --> ui[Pipeline status panel]
  risk --> result[Future UC result tables]
```

## Agent Contracts

### Current Agents

| Agent | File | Inputs | Output | Current persistence |
| --- | --- | --- | --- | --- |
| IngestionManagerAgent | `ingestion.py` | Facilities dataframe, optional `incoming_records` | Upload/schema routing, field presence, column-shift suspicion | Pipeline state JSON |
| QAProfileAgent | `qa.py` | Facilities dataframe, ingestion context | Completeness scores, sparse fields, metadata flags | Pipeline state JSON |
| DedupAgent | `dedup.py` | Facilities dataframe, optional `incoming_records` | Duplicate cluster decisions or ingest insert/update/duplicate/review decisions | Pipeline state JSON |
| EvidenceSpecialtyAgent | `evidence.py` | Facilities dataframe, QA context | Capability claims, evidence status, contradiction flags | Pipeline state JSON |
| GeoAgent | `geo.py` | Facilities dataframe, dedup context | Geographic quality flags, coverage gaps, geo score | Pipeline state JSON |
| ShortageAgent | `shortage.py` | Facilities dataframe, dedup context | Shortage areas and capability gaps | Pipeline state JSON |
| HumanReviewGateAgent | `review.py` | Dedup, Evidence, Geo, Shortage outputs | Review queue triggers and material planning impact score | Pipeline state JSON |
| RiskAgent | `risk.py` | Dedup, Evidence, Geo, Shortage, Review outputs | Risk matrix, executive summary, readiness scores | Pipeline state JSON |

## Pipeline State Shape

State is managed in `app/lib/pipeline_state.py`.

```json
{
  "pipeline_id": "abc123",
  "status": "pending|running|completed|failed",
  "mode": "local|databricks|ingest",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "context": {
    "incoming_records": []
  },
  "agents": {
    "ingestion": {"status": "completed", "result": {}},
    "qa": {},
    "dedup": {},
    "evidence": {},
    "geo": {},
    "shortage": {},
    "review": {},
    "risk": {}
  }
}
```

## Runtime Modes

- `PIPELINE_MODE=local`: FastAPI starts an asyncio pipeline in the app process. State is written to `app/state/pipeline_{id}.json`.
- `PIPELINE_MODE=databricks`: FastAPI triggers a Databricks multi-task Job. Each task runs `app/jobs/run_agent.py <agent> <pipeline_id>`.

## Databricks Job Deployment State

The job definition is scaffolded by `scripts/setup_dbx_job.py`, but Databricks Job mode is not considered verified until:

1. `python scripts/setup_dbx_job.py` succeeds.
2. `.env` contains `DATABRICKS_PIPELINE_JOB_ID=<job id>`.
3. `app/app.yaml` or deployed app env sets `PIPELINE_MODE=databricks`.
4. `app/app.yaml` or deployed app env sets `DATABRICKS_PIPELINE_JOB_ID=<job id>`.
5. `POST /api/pipeline/start` completes a Databricks run and `GET /api/pipeline/status/{id}` shows all eight agents completed.

Until then, deployed apps should keep `PIPELINE_MODE=local` so the pipeline remains clickable.

## Unity Catalog Persistence Gap

Current agent outputs stay in pipeline state JSON. The next persistence work is:

- DedupAgent -> `work.facility_duplicate_candidates`
- EvidenceSpecialtyAgent -> `work.facility_capability_evidence`
- GeoAgent -> `work.data_quality_findings`
- ShortageAgent -> `result.geo_risk_recommendations`
- HumanReviewGateAgent -> `result.reviewer_notes` or `result.action_recommendations`
- RiskAgent -> `result.readiness_kpi_snapshot` and `result.action_recommendations`
