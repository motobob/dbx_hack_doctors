-- Data Readiness Desk Unity Catalog state model.
--
-- Default recommendation:
--   1. Create a dedicated app-owned catalog if allowed.
--   2. If CREATE CATALOG is not allowed, replace `dais_readiness_desk`
--      with an existing writable catalog and create the schemas there.
--
-- Source data stays immutable. Result data is versioned and user/AI
-- mutations are append-only decisions/events.

CREATE CATALOG IF NOT EXISTS dais_readiness_desk
COMMENT 'App-owned catalog for Data Readiness Desk source snapshots, result states, and audit history';

CREATE SCHEMA IF NOT EXISTS dais_readiness_desk.source
COMMENT 'Immutable source snapshots and uploaded raw files';

CREATE SCHEMA IF NOT EXISTS dais_readiness_desk.work
COMMENT 'Intermediate parse, profiling, dedupe, and evidence extraction outputs';

CREATE SCHEMA IF NOT EXISTS dais_readiness_desk.result
COMMENT 'Versioned resulting state used by recommendations, actions, and risks';

CREATE SCHEMA IF NOT EXISTS dais_readiness_desk.audit
COMMENT 'Append-only app, import, reparse, and decision events';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.source.source_snapshots (
  source_snapshot_id STRING NOT NULL,
  source_catalog STRING,
  source_schema STRING,
  source_table STRING,
  source_version STRING,
  source_type STRING,
  row_count BIGINT,
  created_at TIMESTAMP,
  created_by STRING,
  metadata_json STRING
)
USING DELTA
COMMENT 'Immutable source data snapshot metadata';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.source.raw_facilities_snapshot (
  source_snapshot_id STRING NOT NULL,
  source_record_id STRING,
  raw_row_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Optional immutable copy of source facility rows for a source snapshot';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.source.raw_uploaded_files (
  upload_id STRING NOT NULL,
  source_snapshot_id STRING,
  file_name STRING,
  source_name STRING,
  row_count BIGINT,
  parse_status STRING,
  uploaded_at TIMESTAMP,
  uploaded_by STRING,
  metadata_json STRING
)
USING DELTA
COMMENT 'Uploaded file metadata before rows are staged or parsed';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.source.raw_uploaded_rows (
  upload_id STRING NOT NULL,
  row_number BIGINT,
  raw_row_json STRING,
  parse_errors_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw uploaded rows preserved as immutable JSON payloads';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.parse_runs (
  run_id STRING NOT NULL,
  source_snapshot_id STRING NOT NULL,
  scratchpad_version_id STRING,
  run_status STRING,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  triggered_by STRING,
  trigger_type STRING,
  error_message STRING,
  metadata_json STRING
)
USING DELTA
COMMENT 'Each re-parse attempt from source snapshot plus scratchpad context';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.facility_records_normalized (
  run_id STRING NOT NULL,
  source_snapshot_id STRING NOT NULL,
  source_record_id STRING,
  normalized_record_id STRING,
  facility_name STRING,
  address STRING,
  city STRING,
  district STRING,
  state STRING,
  pin_code STRING,
  latitude DOUBLE,
  longitude DOUBLE,
  phone STRING,
  specialties_json STRING,
  description STRING,
  source_json STRING,
  normalized_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Normalized facility records produced by a parse run';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.facility_duplicate_candidates (
  run_id STRING NOT NULL,
  candidate_id STRING NOT NULL,
  left_record_id STRING,
  right_record_id STRING,
  match_confidence DOUBLE,
  match_reasons_json STRING,
  planning_impact STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Pairwise or cluster-level duplicate candidates with explainable match reasons';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.facility_capability_evidence (
  run_id STRING NOT NULL,
  evidence_id STRING NOT NULL,
  normalized_record_id STRING,
  capability STRING,
  claim_status STRING,
  confidence DOUBLE,
  source_field STRING,
  evidence_text STRING,
  reason STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Evidence extracted from structured and free-text facility records';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.data_quality_findings (
  run_id STRING NOT NULL,
  finding_id STRING NOT NULL,
  normalized_record_id STRING,
  issue_type STRING,
  severity STRING,
  confidence DOUBLE,
  recommended_action STRING,
  owner STRING,
  evidence_json STRING,
  planning_impact STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Data readiness findings produced by profiling and evidence extraction';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.pincode_post_offices_clean (
  run_id STRING NOT NULL,
  pincode_str STRING,
  circle_raw STRING,
  region_raw STRING,
  division_raw STRING,
  office_name_raw STRING,
  office_type_raw STRING,
  delivery_raw STRING,
  district_raw STRING,
  state_raw STRING,
  state_norm STRING,
  district_norm STRING,
  district_display STRING,
  latitude_raw STRING,
  longitude_raw STRING,
  latitude_corrected DOUBLE,
  longitude_corrected DOUBLE,
  coord_status STRING,
  quality_flags_json STRING,
  cleaned_at TIMESTAMP
)
USING DELTA
COMMENT 'Cleaned India Post PIN directory at post-office grain; never join facilities directly to this table';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.pincode_lookup_clean (
  run_id STRING NOT NULL,
  pincode_str STRING NOT NULL,
  post_office_count BIGINT,
  office_type_set_json STRING,
  delivery_status_set_json STRING,
  state_count BIGINT,
  district_count BIGINT,
  region_count BIGINT,
  division_count BIGINT,
  circle_count BIGINT,
  canonical_state STRING,
  primary_district STRING,
  primary_district_share DOUBLE,
  latitude_centroid DOUBLE,
  longitude_centroid DOUBLE,
  valid_coord_count BIGINT,
  missing_coord_count BIGINT,
  invalid_coord_count BIGINT,
  coord_swapped_count BIGINT,
  coord_lat_equals_lon_count BIGINT,
  max_coord_span_km_rough DOUBLE,
  has_multi_state BOOLEAN,
  has_multi_district BOOLEAN,
  has_missing_state BOOLEAN,
  has_missing_district BOOLEAN,
  has_coord_quality_issue BOOLEAN,
  pin_confidence_tier STRING,
  pin_quality_score DOUBLE,
  aggregation_flags_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'One-row-per-PIN lookup table safe for facility enrichment without row fan-out';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.pincode_ambiguity_flags (
  run_id STRING NOT NULL,
  pincode_str STRING NOT NULL,
  flag_type STRING,
  severity STRING,
  state_count BIGINT,
  district_count BIGINT,
  evidence_json STRING,
  recommended_action STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Ambiguous or unsafe PIN geography findings for review and downstream caveats';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.pincode_review_queue (
  run_id STRING NOT NULL,
  review_id STRING NOT NULL,
  pincode_str STRING,
  issue_type STRING,
  priority STRING,
  recommendation STRING,
  evidence_json STRING,
  status STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Human review queue for multi-state, weak district, missing geo, or unsafe PIN-derived assignments';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.nfhs_district_indicators_clean (
  run_id STRING NOT NULL,
  state_ut_raw STRING,
  district_name_raw STRING,
  state_ut_norm STRING,
  district_name_norm STRING,
  district_join_key STRING,
  survey_period STRING,
  source_name STRING,
  source_table STRING,
  households_surveyed DOUBLE,
  women_15_49_interviewed DOUBLE,
  men_15_54_interviewed DOUBLE,
  suppressed_cell_count BIGINT,
  caution_cell_count BIGINT,
  parse_failed_cell_count BIGINT,
  row_quality_tier STRING,
  cleaned_at TIMESTAMP,
  indicators_json STRING
)
USING DELTA
COMMENT 'Cleaned NFHS-5 district survey indicators with normalized geography keys and caveat counts';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.nfhs_indicator_quality_flags (
  run_id STRING NOT NULL,
  flag_id STRING NOT NULL,
  state_ut_norm STRING,
  district_name_norm STRING,
  district_join_key STRING,
  indicator_name STRING,
  raw_value STRING,
  parsed_value DOUBLE,
  flag_type STRING,
  severity STRING,
  explanation STRING,
  source_period STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Long-form NFHS survey ingestion caveats: suppressed, caution, parse, range, and geography warnings';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.work.nfhs_geography_review_queue (
  run_id STRING NOT NULL,
  review_id STRING NOT NULL,
  state_ut_raw STRING,
  district_name_raw STRING,
  issue_type STRING,
  priority STRING,
  recommendation STRING,
  evidence_json STRING,
  status STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Human review queue for NFHS geography/key issues only';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.scratchpad_versions (
  scratchpad_version_id STRING NOT NULL,
  parent_scratchpad_version_id STRING,
  markdown STRING,
  tags_json STRING,
  created_at TIMESTAMP,
  created_by STRING
)
USING DELTA
COMMENT 'Versioned Markdown scratchpad used to steer parse and review workflow';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.result_state_versions (
  state_version_id STRING NOT NULL,
  parent_state_version_id STRING,
  run_id STRING NOT NULL,
  source_snapshot_id STRING NOT NULL,
  scratchpad_version_id STRING,
  state_status STRING,
  consistency_score DOUBLE,
  expected_lift_points DOUBLE,
  created_at TIMESTAMP,
  created_by STRING,
  metadata_json STRING
)
USING DELTA
COMMENT 'Materialized resulting state versions produced from parse runs and decisions';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.facility_entities (
  state_version_id STRING NOT NULL,
  facility_entity_id STRING NOT NULL,
  canonical_name STRING,
  city STRING,
  district STRING,
  state STRING,
  pin_code STRING,
  latitude DOUBLE,
  longitude DOUBLE,
  specialties_json STRING,
  capabilities_json STRING,
  source_record_ids_json STRING,
  trust_score DOUBLE,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Current facility entities for a given result state version';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.readiness_kpi_snapshot (
  state_version_id STRING NOT NULL,
  metric_name STRING NOT NULL,
  metric_value DOUBLE,
  metric_unit STRING,
  component_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Readiness KPI metrics for a result state version';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.action_recommendations (
  state_version_id STRING NOT NULL,
  action_id STRING NOT NULL,
  priority STRING,
  issue_type STRING,
  recommendation STRING,
  owner STRING,
  confidence STRING,
  status STRING,
  lift_points DOUBLE,
  evidence_json STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Recommended cleanup/review actions generated from resulting state';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.geo_risk_recommendations (
  state_version_id STRING NOT NULL,
  risk_id STRING NOT NULL,
  priority STRING,
  geography_level STRING,
  geography_value STRING,
  care_need STRING,
  risk_label STRING,
  confidence STRING,
  reason STRING,
  look_at_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Risk recommendations generated only from resulting state';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.reviewer_notes (
  note_id STRING NOT NULL,
  state_version_id STRING,
  target_type STRING,
  target_id STRING,
  note_markdown STRING,
  tags_json STRING,
  created_at TIMESTAMP,
  created_by STRING
)
USING DELTA
COMMENT 'Reviewer comments and tags attached to actions, risks, facilities, or state versions';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.result.action_decisions (
  decision_id STRING NOT NULL,
  state_version_id STRING NOT NULL,
  action_id STRING NOT NULL,
  decision STRING,
  decision_note STRING,
  decided_at TIMESTAMP,
  decided_by STRING
)
USING DELTA
COMMENT 'Append-only human or AI decisions on generated action recommendations';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.app_events (
  event_id STRING NOT NULL,
  event_type STRING,
  actor STRING,
  target_type STRING,
  target_id STRING,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only operational event stream for the app';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.reparse_events (
  event_id STRING NOT NULL,
  run_id STRING,
  state_version_id STRING,
  event_type STRING,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only event stream for re-parse runs and state materialization';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.import_events (
  event_id STRING NOT NULL,
  upload_id STRING,
  event_type STRING,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only import workflow events';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.pincode_ingestion_log (
  event_id STRING NOT NULL,
  run_id STRING,
  raw_pincode_table STRING,
  raw_row_count BIGINT,
  exact_duplicate_rows BIGINT,
  invalid_pincode_rows BIGINT,
  coord_missing_rows BIGINT,
  coord_parse_failed_rows BIGINT,
  coord_swapped_rows BIGINT,
  coord_outside_india_rows BIGINT,
  coord_lat_equals_lon_rows BIGINT,
  unique_pincode_count BIGINT,
  multi_state_pincode_count BIGINT,
  multi_district_pincode_count BIGINT,
  tier_a_count BIGINT,
  tier_b_count BIGINT,
  tier_c_count BIGINT,
  tier_d_count BIGINT,
  queued_for_review BIGINT,
  avg_post_office_quality_score DOUBLE,
  avg_pincode_quality_score DOUBLE,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only run summaries for the PIN directory ingestion/enrichment workflow';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.nfhs_ingestion_log (
  event_id STRING NOT NULL,
  run_id STRING,
  raw_nfhs_table STRING,
  raw_row_count BIGINT,
  column_count BIGINT,
  distinct_state_ut_count BIGINT,
  distinct_district_key_count BIGINT,
  duplicate_district_key_count BIGINT,
  suppressed_cell_count BIGINT,
  caution_estimate_cell_count BIGINT,
  parse_failed_cell_count BIGINT,
  pct_out_of_range_count BIGINT,
  geography_review_count BIGINT,
  tier_a_count BIGINT,
  tier_b_count BIGINT,
  tier_c_count BIGINT,
  tier_d_count BIGINT,
  avg_ingestion_quality_score DOUBLE,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only run summaries for the NFHS-5 survey ingestion workflow';

CREATE TABLE IF NOT EXISTS dais_readiness_desk.audit.decision_events (
  event_id STRING NOT NULL,
  decision_id STRING,
  state_version_id STRING,
  action_id STRING,
  event_type STRING,
  event_json STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Append-only decision and reviewer mutation history';
