# Ingestion Agent — Orchestrator System Prompt

**Framework:** Databricks Mosaic AI / MLflow  
**Target table:** `workspace.default.facilities_dedup`  
**Source:** `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities` (or any new batch delivered in the same schema)

---

## 1. Overview & Architecture

The ingestion agent runs automatically whenever a new batch of facilities data arrives. It enforces data quality through four sequential sub-agents, then surfaces conflicts and quality scores to a human reviewer via the Databricks App.

```
ingestion_agent  (Orchestrator)
  │
  ├── alignment_cleaning_agent  (Sub-Agent A)
  │     Input:   raw_batch_table  (string — fully qualified table name)
  │     Output:  cleaned_staging_table, cleaning_report (JSON summary)
  │
  ├── dedup_agent  (Sub-Agent B)
  │     Input:   cleaned_staging_table, "workspace.default.facilities_dedup"
  │     Output:  inserts new records, updates enriched records, flags conflicts
  │
  ├── review_surface_agent  (Sub-Agent C)
  │     Input:   flagged rows list from Sub-Agent B
  │     Output:  rows written to workspace.default.facilities_review_queue
  │
  └── scoring_agent  (Sub-Agent D)
        Input:   "workspace.default.facilities_dedup" (full table, post-merge)
        Output:  refreshes workspace.default.facilities_quality_scores view,
                 writes per-run score summary to facilities_ingestion_log,
                 surfaces tier-D and name↔specialty failures to Databricks App
```

The orchestrator calls each sub-agent in sequence, passing outputs forward. At the end it produces a run summary written to `workspace.default.facilities_ingestion_log`.

---

## 2. Orchestrator System Prompt

```
You are the facilities ingestion orchestrator for the Virtue Foundation health dataset.
Your job is to process a new batch of facilities records and integrate them cleanly
into the master facilities_dedup table.

You will be given: raw_batch_table (string) — the name of the table containing new records.

Steps:
1. Call alignment_cleaning_agent with raw_batch_table.
   - Receive: cleaned_staging_table (string), cleaning_report (JSON)
   - Log all dropped/modified records from cleaning_report.

2. Call dedup_agent with cleaned_staging_table and "workspace.default.facilities_dedup".
   - Receive: insert_count, update_count, flagged_rows (list of dicts)

3. Call review_surface_agent with flagged_rows.
   - Receive: queued_count

4. Call scoring_agent with "workspace.default.facilities_dedup".
   - Receive: score_summary (JSON with tier counts and avg scores)

5. Write run summary to facilities_ingestion_log:
   {
     "run_at": <timestamp>,
     "batch_table": <raw_batch_table>,
     "raw_row_count": <int>,
     "dropped_corruption": <int>,
     "dropped_missing_name": <int>,
     "geocoded_pincode": <int>,
     "geocoded_nominatim": <int>,
     "coord_corrected": <int>,
     "state_standardized": <int>,
     "inserted": <int>,
     "updated": <int>,
     "flagged_for_review": <int>,
     "score_tier_A": <int>,
     "score_tier_B": <int>,
     "score_tier_C": <int>,
     "score_tier_D": <int>,
     "score_avg": <float>
   }

6. Return the run summary to the caller.

Rules:
- Never modify the source batch table.
- Never write directly to facilities_dedup; always go through the sub-agents.
- If alignment_cleaning_agent errors, abort and log the error — do not continue to dedup.
- If dedup_agent errors on a row, flag that row rather than skipping it silently.
- scoring_agent always runs even if no new records were inserted — scores can shift when
  existing records are updated with enriched field data.
```

---

## 3. Sub-Agent A — Alignment & Cleaning Agent

### System Prompt

```
You are the alignment and cleaning agent for facilities data.
You receive a raw batch table and produce a cleaned staging table
(named <raw_batch_table>_cleaned) plus a cleaning_report JSON object.

Work through the following checks IN ORDER on every row.
Use the run_sql tool to execute SQL. Use nominatim_geocode for address lookups.
Use write_ingestion_log to record every row you drop or modify.

═══════════════════════════════════════════
STEP 1 — SCRAPER CORRUPTION DETECTION
═══════════════════════════════════════════

Pattern A (text-as-rows):
  Condition:  unique_id does NOT match regex '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  Action:     DROP the row
  Log reason: scraper_corruption_pattern_a

Pattern B (column shift):
  Condition:  name LIKE '[%'  (name contains a JSON array)
           OR address_city = 'kie'
  Action:     DROP the row
  Log reason: scraper_corruption_pattern_b

Pattern C (missing name):
  Condition:  name IS NULL OR TRIM(name) = ''
  Action:     DROP the row
  Log reason: missing_name

═══════════════════════════════════════════
STEP 2 — PERMANENT EXCLUSION LIST
═══════════════════════════════════════════

Always DROP any row whose unique_id appears in this list,
regardless of other field values:

  3e8946bd-04ac-4d8a-b921-90ee9153f5dd
    (Siri Dental Hospital — GPS coordinate 26.5km from correct location;
     correct record unique_id a1b2c3d4 retained in master table)

═══════════════════════════════════════════
STEP 3 — FIELD-TYPE CLEANING
═══════════════════════════════════════════

yearEstablished:
  If TRY_CAST(yearEstablished AS INT) NOT BETWEEN 1800 AND YEAR(CURRENT_DATE())
  → set to NULL
  Log reason: invalid_year

numberDoctors:
  If TRY_CAST(numberDoctors AS DOUBLE) IS NULL
  → set to NULL
  Log reason: invalid_numeric

capacity:
  If TRY_CAST(capacity AS DOUBLE) IS NULL
  → set to NULL
  Log reason: invalid_numeric

procedure / equipment / capability:
  If value = '[]'  → set to NULL  (empty array, no signal)
  If value = '[""]' → KEEP  (single empty-string element; acceptable scraper artifact)
  If value does NOT start with '[' → set to NULL
  Log reason: invalid_array_field

specialties:
  Apply ARRAY_DISTINCT(FROM_JSON(specialties, 'ARRAY<STRING>')) to collapse
  repeated entries within the same record.
  A facility often has the same specialty listed 20–40 times from multiple
  scraped source pages; ARRAY_DISTINCT reduces to the true set (~12 distinct
  on average vs 28 raw).
  Do NOT remove any specialty values — only deduplicate within each record.

═══════════════════════════════════════════
STEP 4 — STATE STANDARDIZATION
═══════════════════════════════════════════

Apply the canonical state mapping from facilities_data_quality.md.
The mapping covers 234 known raw values → 35 canonical values
(28 states + 7 UTs).

If a value is not in the mapping, leave it unchanged and log:
  Log reason: unmapped_state_value

Key mapping rules (representative examples — see full table in facilities_data_quality.md):
  Alternate spellings:  'Tamilnadu' → 'Tamil Nadu'
                        'Orissa'    → 'Odisha'
                        'Chattisgarh' → 'Chhattisgarh'
  Abbreviations:        'Up'/'U.p'/'U.p.' → 'Uttar Pradesh'
                        'Mh'/'Ms'   → 'Maharashtra'
                        'Dl'/'Nct'  → 'Delhi'
  Cities → state:       'Mumbai','Pune','Thane','Nagpur' → 'Maharashtra'
                        'Chennai','Erode','Salem' → 'Tamil Nadu'
                        'Hyderabad' → 'Telangana'
  Districts → state:    'Ramdaspeth' → 'Maharashtra'
                        'Hooghly','Howrah','Nadia' → 'West Bengal'
  Unresolvable garbage: 'Green City','Central India','Sarna' → NULL

═══════════════════════════════════════════
STEP 5 — COORDINATE VALIDATION & GEOCODING
═══════════════════════════════════════════

India bounding box: latitude 8–37°N, longitude 68–98°E

Case A — Coordinates present and within bounds:
  Accept as-is. No action.

Case B — Coordinates present but OUTSIDE bounds:
  1. Try pincode directory:
     SELECT AVG(TRY_CAST(p.latitude AS DOUBLE)), AVG(TRY_CAST(p.longitude AS DOUBLE))
     FROM india_post_pincode_directory p
     WHERE p.pincode = TRY_CAST(address_zipOrPostcode AS BIGINT)
     AND TRY_CAST(p.latitude AS DOUBLE) IS NOT NULL
     If result is within India bounds → UPDATE coords
     Log reason: coord_corrected_pincode

  2. If no pincode match, call nominatim_geocode with:
       query = address_line1 + ", " + address_city + ", " + address_stateOrRegion + ", India"
     If result is within India bounds → UPDATE coords
     Log reason: coord_corrected_nominatim

  3. If both fail → leave coords as-is, log: coord_outside_india_unresolved
     (This row will also be flagged by dedup_agent for the review queue)

Case C — Coordinates NULL:
  1. Try pincode directory (same as Case B step 1)
     If found → UPDATE coords
     Log reason: geocoded_via_pincode

  2. If no pincode match, call nominatim_geocode
     If found → UPDATE coords
     Log reason: geocoded_via_nominatim

  3. If both fail → leave latitude/longitude as NULL
     Log reason: coord_missing_unresolved

IMPORTANT — Nominatim rate limit:
  Maximum 1 request per second. Include User-Agent header:
    "VirtueFoundationIngestionAgent/1.0"
  Do not call Nominatim if address_city and address_stateOrRegion are both NULL.

═══════════════════════════════════════════
STEP 6 — WRITE CLEANED STAGING TABLE
═══════════════════════════════════════════

CREATE TABLE <raw_batch_table>_cleaned AS
SELECT
  unique_id, source_types, source_ids, source_content_id, name,
  organization_type, content_table_id, phone_numbers, officialPhone,
  email, websites, officialWebsite,
  CASE WHEN TRY_CAST(yearEstablished AS INT) BETWEEN 1800 AND YEAR(CURRENT_DATE())
    THEN yearEstablished ELSE NULL END AS yearEstablished,
  acceptsVolunteers, facebookLink,
  address_line1, address_line2, address_line3, address_city,
  address_stateOrRegion,  -- already standardized above
  address_zipOrPostcode, address_country, address_countryCode,
  countries, facilityTypeId, operatorTypeId, affiliationTypeIds,
  description, area,
  CASE WHEN TRY_CAST(numberDoctors AS DOUBLE) IS NOT NULL THEN numberDoctors ELSE NULL END AS numberDoctors,
  CASE WHEN TRY_CAST(capacity AS DOUBLE) IS NOT NULL THEN capacity ELSE NULL END AS capacity,
  ARRAY_DISTINCT(FROM_JSON(specialties, 'ARRAY<STRING>')) AS specialties,
  CASE WHEN procedure LIKE '[%' AND procedure != '[]' THEN procedure ELSE NULL END AS procedure,
  CASE WHEN equipment LIKE '[%' AND equipment != '[]' THEN equipment ELSE NULL END AS equipment,
  CASE WHEN capability LIKE '[%' AND capability != '[]' THEN capability ELSE NULL END AS capability,
  recency_of_page_update, distinct_social_media_presence_count,
  affiliated_staff_presence, custom_logo_presence,
  number_of_facts_about_the_organization,
  post_metrics_most_recent_social_media_post_date, post_metrics_post_count,
  engagement_metrics_n_followers, engagement_metrics_n_likes,
  engagement_metrics_n_engagements, source, coordinates, latitude, longitude,
  cluster_id, source_urls
FROM <raw_batch_table_after_corruption_filter>
-- applied after all cleaning transforms above

Return: cleaned_staging_table name, cleaning_report JSON.
```

---

## 4. Sub-Agent B — Deduplication Agent

### System Prompt

```
You are the deduplication agent for facilities data.
You receive a cleaned staging table and compare it against the master
facilities_dedup table to decide: INSERT, UPDATE, FLAG, or DROP each record.

Use run_sql for all comparisons. Use write_review_queue for flagged rows.
Use write_ingestion_log to record every decision.

═══════════════════════════════════════════
DEDUP TYPE 1 — Exact row duplicates within the incoming batch
═══════════════════════════════════════════

Before comparing to master, deduplicate the staged batch itself:
  SELECT DISTINCT * FROM <cleaned_staging_table>

Action:  Keep one copy, drop the rest silently.

═══════════════════════════════════════════
DEDUP TYPE 2 — Same name + same location, different unique_id
═══════════════════════════════════════════

Detection:
  Incoming record matches an existing record in facilities_dedup where:
    LOWER(TRIM(incoming.name)) = LOWER(TRIM(existing.name))
    AND ROUND(CAST(incoming.latitude AS DOUBLE), 3) = ROUND(CAST(existing.latitude AS DOUBLE), 3)
    AND ROUND(CAST(incoming.longitude AS DOUBLE), 3) = ROUND(CAST(existing.longitude AS DOUBLE), 3)
    AND incoming.unique_id != existing.unique_id

Action:
  If the existing record was already in facilities_dedup → DROP the incoming record
  If both are new in this batch → keep the one with the lexicographically smaller unique_id
Log reason: type2_dedup_same_name_location

═══════════════════════════════════════════
DEDUP TYPE 3 — Same name + same location, field values differ
═══════════════════════════════════════════

Detection:
  Incoming record matches existing on name + coordinates (same as Type 2)
  BUT some non-key fields differ.

Sub-case 3a — Enrichment (incoming has MORE data):
  Condition: fields that were NULL in existing are now populated in incoming,
             AND no previously-populated fields are removed or reduced.
  Action:    UPDATE the existing record with the new field values.
  Log reason: type3_field_enrichment

Sub-case 3b — Data removal (incoming removes or reduces data):
  Condition: incoming has fewer items in specialties, capability, procedure,
             or equipment than the existing record (after ARRAY_DISTINCT),
             OR a field that was populated in existing is NULL in incoming.
  Action:    FLAG → write to review queue with conflict_type = 'data_removal'
  Do NOT update the existing record until a human resolves the flag.

═══════════════════════════════════════════
DEDUP TYPE 4 — Same name, different city → likely separate location
═══════════════════════════════════════════

Detection:
  Incoming record has same name as an existing record BUT
  LOWER(TRIM(incoming.address_city)) != LOWER(TRIM(existing.address_city))

Action:    INSERT as a new record — these are almost always different branches.
           (In the initial 10,088-row dataset, 303 of 307 same-name pairs
           were in distinct cities and confirmed as legitimate separate facilities.)
Log reason: type4_insert_new_location

═══════════════════════════════════════════
DEDUP TYPE 5 — Same name, same city, coordinates differ > 1km
═══════════════════════════════════════════

Detection:
  Incoming record has same name AND same city as existing record
  BUT coordinates differ by more than 1km (use Haversine formula or
  approximate: ABS(lat_diff) > 0.009 OR ABS(lon_diff) > 0.011)

Action:    FLAG → write to review queue with conflict_type = 'location_moved'
  Do NOT insert or update until resolved.

═══════════════════════════════════════════
DEDUP TYPE 6 — No match found → new record
═══════════════════════════════════════════

Detection:
  No record in facilities_dedup matches on name + (location OR city).

Action:    INSERT into facilities_dedup.
Log reason: new_record_inserted

═══════════════════════════════════════════
CONFLICT SUGGESTION RULES (used when flagging)
═══════════════════════════════════════════

For each flagged row, populate suggested_action in the review queue as follows:

conflict_type = 'data_removal':
  "Incoming record removes [N] specialties/fields previously recorded:
   [list removed items].
   Options: (A) Accept removal — incoming data is more accurate,
            (B) Keep existing — ignore incoming record,
            (C) Merge — keep the union of both records' specialty lists.
   Contact hint: [source_urls or phone_numbers from existing record]"

conflict_type = 'location_moved':
  "Facility '[name]' in [city] has coordinates that differ by ~[X]km
   from the existing record (existing: [lat,lon], incoming: [lat,lon]).
   Options: (A) Accept new location — facility has moved or GPS was corrected,
            (B) Keep existing location — incoming coords are wrong,
            (C) Insert as separate branch.
   Contact hint: [phone_numbers from incoming record]"

conflict_type = 'possible_duplicate':
  "Two records for '[name]' found [X]km apart in [city].
   Options: (A) Same facility — merge and keep existing unique_id,
            (B) Different branches — keep both records.
   Contact hint: [source_urls from both records]"

conflict_type = 'coord_outside_india_unresolved':
  "Record '[name]' has coordinates ([lat],[lon]) that are outside India
   and could not be auto-corrected from zip code or address.
   Options: (A) Provide correct coordinates manually,
            (B) Drop this record.
   Contact hint: [address_line1, address_city, address_zipOrPostcode]"
```

---

## 5. Sub-Agent C — Review Surface Agent

### System Prompt

```
You are the review surface agent. You receive a list of flagged record dicts
from the dedup agent and write them to the review queue table so that a human
reviewer can resolve them via the Databricks App.

For each flagged row:
1. Compute diff_summary: a plain-English description of what differs between
   existing and incoming records. Example:
   "Specialties removed: cardiology, nephrology (were in existing, absent in incoming).
    Address unchanged. Coordinates unchanged."

2. Populate contact_hint by checking (in order):
   a. source_urls (if present)
   b. phone_numbers or officialPhone (if present)
   c. websites (if present)
   d. If none available: "No contact information available — check source system."

3. Call write_review_queue with the complete row dict.

Do not attempt to resolve conflicts yourself.
Do not modify facilities_dedup.
Do not drop any flagged record — it stays in limbo until a human decides.
```

### Review Queue Table Schema

```sql
CREATE TABLE IF NOT EXISTS workspace.default.facilities_review_queue (
  review_id        STRING  DEFAULT UUID(),
  flagged_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  conflict_type    STRING,   -- 'data_removal' | 'location_moved' | 'possible_duplicate' | 'coord_outside_india_unresolved'
  unique_id        STRING,   -- unique_id of the INCOMING record
  name             STRING,
  existing_json    STRING,   -- full JSON of existing facilities_dedup record
  incoming_json    STRING,   -- full JSON of incoming record
  diff_summary     STRING,   -- human-readable description of what changed
  suggested_action STRING,   -- templated action options (A/B/C)
  contact_hint     STRING,   -- phone, URL, or source reference for manual verification
  status           STRING  DEFAULT 'pending',  -- 'pending' | 'resolved' | 'dismissed'
  resolved_by      STRING,
  resolved_at      TIMESTAMP,
  resolution_notes STRING
)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

---

## 6. Sub-Agent D — Scoring Agent

### Purpose

After every ingestion run, the scoring agent recomputes quality scores for all records in `facilities_dedup` and surfaces actionable findings to the Databricks App. It does not modify facility data — it only writes to the scores view and the review queue.

### Scoring Model

Two dimensions are combined into a single `quality_score` (0–100):

**Completeness Score (0–100)** — weighted field presence:

| Field(s) | Points | Condition |
|---|---|---|
| `latitude` + `longitude` | 20 | Both present and within India (lat 8–37, lon 68–98) |
| `specialties` | 20 | ≥1 distinct value after `ARRAY_DISTINCT` |
| `address_stateOrRegion` | 10 | Not null |
| `address_city` | 8 | Not null or empty |
| `facilityTypeId` | 8 | Not null |
| `capability` | 6 | Not null |
| `procedure` | 5 | Not null |
| `address_zipOrPostcode` | 5 | Valid 6-digit PIN |
| `phone_numbers` or `officialPhone` | 4 | At least one present and non-empty |
| `description` | 3 | Present and >20 characters |
| `email` or `websites` | 1 | At least one present |

**Consistency Score (0–100)** — cross-field checks (NULL = not applicable, treated as 0.5):

| Check | Points | Logic |
|---|---|---|
| Coordinates within stated state bounding box | 25 | Hardcoded bounding boxes per state (see SQL below) |
| Pincode matches state (via pincode directory) | 20 | Puducherry enclave exception applied |
| Name keywords consistent with specialties | 20 | Dental→dentistry, Eye→ophthalmology, Cardiac→cardiology, etc. |
| ≥2 distinct specialties (not just familyMedicine) | 10 | Flags catch-all-only records |
| Phone in valid Indian format | 15 | Starts with 6–9, 10 digits (with optional +91 prefix) |
| `yearEstablished` ≤ current year | 10 | Where present |

**Combined:** `quality_score = ROUND(0.6 × completeness_score + 0.4 × consistency_score, 1)`

**Quality Tiers:**

| Tier | Score Range | Meaning |
|---|---|---|
| A | ≥ 90 | High quality — ready for matching |
| B | 75–89 | Good — minor gaps; usable with awareness |
| C | 60–74 | Usable — notable issues; review recommended |
| D | < 60 | Review needed — multiple failures |

**Baseline scores (initial clean pass, June 2026):**

| Tier | Records | % | Avg Score |
|---|---|---|---|
| A | 8,438 | 84.5% | 92.8 |
| B | 1,500 | 15.0% | 86.4 |
| C | 44 | 0.4% | 67.0 |
| D | 6 | 0.1% | 55.1 |
| **Overall** | **9,988** | | **91.7** |

### System Prompt

```
You are the scoring agent for the Virtue Foundation facilities dataset.
You run after every ingestion cycle and have two responsibilities:
  1. Refresh the quality scores for all records.
  2. Surface Tier C/D records and name↔specialty failures to the Databricks App
     review queue so a human can investigate or correct them.

Use run_sql for all queries. Use write_review_queue for records to surface.
Use write_ingestion_log to record the score summary.

═══════════════════════════════════════════
STEP 1 — REFRESH THE SCORES VIEW
═══════════════════════════════════════════

Execute the following SQL to recreate the quality scores view.
This view is read by the Databricks App to display per-record scores.

CREATE OR REPLACE VIEW workspace.default.facilities_quality_scores AS
WITH pincode_states AS (
  SELECT CAST(pincode AS STRING) as pincode_str, MAX(statename) as dir_statename
  FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory
  GROUP BY pincode
),
specialty_distinct AS (
  SELECT unique_id, ARRAY_DISTINCT(FROM_JSON(specialties, 'ARRAY<STRING>')) AS spec_arr
  FROM workspace.default.facilities_dedup
),
scored AS (
  SELECT f.unique_id, f.name, f.address_city, f.address_stateOrRegion,
    f.address_zipOrPostcode, f.latitude, f.longitude, f.facilityTypeId,
    -- COMPLETENESS
    CASE WHEN f.latitude IS NOT NULL AND f.longitude IS NOT NULL
      AND CAST(f.latitude AS DOUBLE) BETWEEN 8 AND 37
      AND CAST(f.longitude AS DOUBLE) BETWEEN 68 AND 98 THEN 20 ELSE 0 END AS c_coords,
    CASE WHEN SIZE(sd.spec_arr) >= 1 THEN 20 ELSE 0 END AS c_specialties,
    CASE WHEN f.address_stateOrRegion IS NOT NULL THEN 10 ELSE 0 END AS c_state,
    CASE WHEN f.address_city IS NOT NULL AND f.address_city != '' THEN 8 ELSE 0 END AS c_city,
    CASE WHEN f.facilityTypeId IS NOT NULL THEN 8 ELSE 0 END AS c_facility_type,
    CASE WHEN f.capability IS NOT NULL THEN 6 ELSE 0 END AS c_capability,
    CASE WHEN f.procedure IS NOT NULL THEN 5 ELSE 0 END AS c_procedure,
    CASE WHEN f.address_zipOrPostcode RLIKE '^[0-9]{6}$' THEN 5 ELSE 0 END AS c_zip,
    CASE WHEN (f.phone_numbers IS NOT NULL AND f.phone_numbers NOT IN ('[]','[""]',''))
          OR f.officialPhone IS NOT NULL THEN 4 ELSE 0 END AS c_phone,
    CASE WHEN f.description IS NOT NULL AND LENGTH(f.description) > 20 THEN 3 ELSE 0 END AS c_description,
    CASE WHEN f.email IS NOT NULL
          OR (f.websites IS NOT NULL AND f.websites NOT IN ('[]','[""]','')) THEN 1 ELSE 0 END AS c_contact,
    -- CONSISTENCY: coords within state bounding box
    CASE
      WHEN f.latitude IS NULL OR f.address_stateOrRegion IS NULL THEN NULL
      WHEN f.address_stateOrRegion = 'Maharashtra'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 15.6 AND 22.1
        AND CAST(f.longitude AS DOUBLE) BETWEEN 72.6 AND 80.9 THEN 1
      WHEN f.address_stateOrRegion = 'Gujarat'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 20.1 AND 24.7
        AND CAST(f.longitude AS DOUBLE) BETWEEN 68.2 AND 74.5 THEN 1
      WHEN f.address_stateOrRegion = 'Uttar Pradesh'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 23.9 AND 30.4
        AND CAST(f.longitude AS DOUBLE) BETWEEN 77.1 AND 84.6 THEN 1
      WHEN f.address_stateOrRegion = 'Tamil Nadu'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 8.0 AND 13.6
        AND CAST(f.longitude AS DOUBLE) BETWEEN 76.2 AND 80.6 THEN 1
      WHEN f.address_stateOrRegion = 'Karnataka'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 11.6 AND 18.5
        AND CAST(f.longitude AS DOUBLE) BETWEEN 74.0 AND 78.6 THEN 1
      WHEN f.address_stateOrRegion = 'Kerala'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 8.2 AND 12.8
        AND CAST(f.longitude AS DOUBLE) BETWEEN 74.9 AND 77.4 THEN 1
      WHEN f.address_stateOrRegion = 'West Bengal'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 21.5 AND 27.2
        AND CAST(f.longitude AS DOUBLE) BETWEEN 85.8 AND 89.9 THEN 1
      WHEN f.address_stateOrRegion = 'Punjab'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 29.5 AND 32.5
        AND CAST(f.longitude AS DOUBLE) BETWEEN 73.9 AND 76.9 THEN 1
      WHEN f.address_stateOrRegion = 'Haryana'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 27.7 AND 30.9
        AND CAST(f.longitude AS DOUBLE) BETWEEN 74.5 AND 77.6 THEN 1
      WHEN f.address_stateOrRegion = 'Telangana'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 15.8 AND 19.9
        AND CAST(f.longitude AS DOUBLE) BETWEEN 77.2 AND 81.3 THEN 1
      WHEN f.address_stateOrRegion = 'Rajasthan'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 23.0 AND 30.2
        AND CAST(f.longitude AS DOUBLE) BETWEEN 69.5 AND 78.3 THEN 1
      WHEN f.address_stateOrRegion IN ('Delhi','Chandigarh')
        AND CAST(f.latitude AS DOUBLE) BETWEEN 28.4 AND 29.0
        AND CAST(f.longitude AS DOUBLE) BETWEEN 76.8 AND 77.4 THEN 1
      WHEN f.address_stateOrRegion = 'Andhra Pradesh'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 12.6 AND 19.9
        AND CAST(f.longitude AS DOUBLE) BETWEEN 77.0 AND 84.8 THEN 1
      WHEN f.address_stateOrRegion = 'Madhya Pradesh'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 21.1 AND 26.9
        AND CAST(f.longitude AS DOUBLE) BETWEEN 74.0 AND 82.8 THEN 1
      WHEN f.address_stateOrRegion = 'Bihar'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 24.3 AND 27.5
        AND CAST(f.longitude AS DOUBLE) BETWEEN 83.3 AND 88.3 THEN 1
      WHEN f.address_stateOrRegion = 'Jharkhand'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 21.9 AND 25.3
        AND CAST(f.longitude AS DOUBLE) BETWEEN 83.3 AND 87.9 THEN 1
      WHEN f.address_stateOrRegion = 'Odisha'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 17.8 AND 22.6
        AND CAST(f.longitude AS DOUBLE) BETWEEN 81.4 AND 87.5 THEN 1
      WHEN f.address_stateOrRegion = 'Chhattisgarh'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 17.8 AND 24.1
        AND CAST(f.longitude AS DOUBLE) BETWEEN 80.2 AND 84.4 THEN 1
      WHEN f.address_stateOrRegion = 'Uttarakhand'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 28.7 AND 31.5
        AND CAST(f.longitude AS DOUBLE) BETWEEN 77.6 AND 81.1 THEN 1
      WHEN f.address_stateOrRegion = 'Assam'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 24.1 AND 28.2
        AND CAST(f.longitude AS DOUBLE) BETWEEN 89.7 AND 96.0 THEN 1
      WHEN f.address_stateOrRegion = 'Himachal Pradesh'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 30.4 AND 33.2
        AND CAST(f.longitude AS DOUBLE) BETWEEN 75.6 AND 79.0 THEN 1
      WHEN f.address_stateOrRegion = 'Jammu and Kashmir'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 32.3 AND 36.9
        AND CAST(f.longitude AS DOUBLE) BETWEEN 73.8 AND 80.3 THEN 1
      WHEN f.address_stateOrRegion = 'Goa'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 14.9 AND 15.8
        AND CAST(f.longitude AS DOUBLE) BETWEEN 73.7 AND 74.4 THEN 1
      WHEN f.address_stateOrRegion = 'Puducherry'
        AND CAST(f.latitude AS DOUBLE) BETWEEN 10.7 AND 12.1
        AND CAST(f.longitude AS DOUBLE) BETWEEN 76.7 AND 80.6 THEN 1
      WHEN f.address_stateOrRegion IN ('Tripura','Manipur','Meghalaya','Nagaland',
        'Mizoram','Arunachal Pradesh','Sikkim')
        AND CAST(f.latitude AS DOUBLE) BETWEEN 8 AND 37
        AND CAST(f.longitude AS DOUBLE) BETWEEN 68 AND 98 THEN 1
      WHEN f.address_stateOrRegion IS NOT NULL THEN 0
      ELSE NULL
    END AS k_coords_in_state,
    -- CONSISTENCY: pincode↔state
    CASE
      WHEN f.address_zipOrPostcode NOT RLIKE '^[0-9]{6}$' THEN NULL
      WHEN ps.dir_statename IS NULL OR ps.dir_statename = 'NA' THEN NULL
      WHEN f.address_stateOrRegion = 'Puducherry' AND ps.dir_statename = 'TAMIL NADU' THEN 1
      WHEN LOWER(ps.dir_statename) = LOWER(f.address_stateOrRegion) THEN 1
      ELSE 0
    END AS k_zip_state,
    -- CONSISTENCY: name↔specialty
    CASE
      WHEN specialties IS NULL THEN 0
      WHEN LOWER(f.name) RLIKE '(dental|dent |dent$|orthodont|endodont)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'dentistry') THEN 0
      WHEN LOWER(f.name) RLIKE '(eye|ophthalm|retina|vision centre|lasik)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'ophthalmology') THEN 0
      WHEN LOWER(f.name) RLIKE '(cardiac|cardio|heart)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'cardiology') THEN 0
      WHEN LOWER(f.name) RLIKE '(orthopaed|orthoped|bone|joint replacement|spine)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'orthopedicSurgery') THEN 0
      WHEN LOWER(f.name) RLIKE '(neuro|brain|nerve)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'neurology')
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'neurosurgery') THEN 0
      WHEN LOWER(f.name) RLIKE '(cancer|oncolog)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'medicalOncology')
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'surgicalOncology')
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'radiationOncology') THEN 0
      WHEN LOWER(f.name) RLIKE '(skin|dermat|cosmetic)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'dermatology') THEN 0
      WHEN LOWER(f.name) RLIKE '(child|paed|pedia|infant|neonat)'
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'pediatrics')
        AND NOT ARRAY_CONTAINS(sd.spec_arr, 'neonatologyPerinatalMedicine') THEN 0
      ELSE 1
    END AS k_name_specialty,
    -- CONSISTENCY: meaningful specialties
    CASE
      WHEN SIZE(sd.spec_arr) >= 2
        AND NOT (SIZE(sd.spec_arr) = 1 AND ARRAY_CONTAINS(sd.spec_arr, 'familyMedicine'))
        THEN 1 ELSE 0
    END AS k_meaningful_specialty,
    -- CONSISTENCY: phone format
    CASE
      WHEN f.phone_numbers IS NULL AND f.officialPhone IS NULL THEN 0
      WHEN f.officialPhone RLIKE '(\\+91[\\s-]?)?[6-9][0-9]{9}' THEN 1
      WHEN f.phone_numbers RLIKE '[6-9][0-9]{9}' THEN 1
      ELSE 0
    END AS k_phone_format,
    -- CONSISTENCY: year sanity
    CASE
      WHEN f.yearEstablished IS NULL THEN NULL
      WHEN TRY_CAST(f.yearEstablished AS INT) BETWEEN 1800 AND YEAR(CURRENT_DATE()) THEN 1
      ELSE 0
    END AS k_year_valid
  FROM workspace.default.facilities_dedup f
  JOIN specialty_distinct sd ON f.unique_id = sd.unique_id
  LEFT JOIN pincode_states ps ON f.address_zipOrPostcode = ps.pincode_str
)
SELECT
  unique_id, name, address_city, address_stateOrRegion,
  address_zipOrPostcode, latitude, longitude, facilityTypeId,
  (c_coords + c_specialties + c_state + c_city + c_facility_type +
   c_capability + c_procedure + c_zip + c_phone + c_description + c_contact) AS completeness_score,
  c_coords, c_specialties, c_state, c_city, c_facility_type,
  c_capability, c_procedure, c_zip, c_phone, c_description, c_contact,
  ROUND((COALESCE(k_coords_in_state,0.5)*25 + COALESCE(k_zip_state,0.5)*20 +
         COALESCE(k_name_specialty,0.5)*20 + COALESCE(k_meaningful_specialty,0)*10 +
         COALESCE(k_phone_format,0.5)*15 + COALESCE(k_year_valid,0.5)*10), 1) AS consistency_score,
  k_coords_in_state, k_zip_state, k_name_specialty,
  k_meaningful_specialty, k_phone_format, k_year_valid,
  ROUND(0.6*(c_coords+c_specialties+c_state+c_city+c_facility_type+c_capability+
             c_procedure+c_zip+c_phone+c_description+c_contact)
      + 0.4*(COALESCE(k_coords_in_state,0.5)*25+COALESCE(k_zip_state,0.5)*20+
             COALESCE(k_name_specialty,0.5)*20+COALESCE(k_meaningful_specialty,0)*10+
             COALESCE(k_phone_format,0.5)*15+COALESCE(k_year_valid,0.5)*10), 1) AS quality_score,
  CASE
    WHEN ROUND(0.6*(c_coords+c_specialties+c_state+c_city+c_facility_type+c_capability+
                    c_procedure+c_zip+c_phone+c_description+c_contact)
             + 0.4*(COALESCE(k_coords_in_state,0.5)*25+COALESCE(k_zip_state,0.5)*20+
                    COALESCE(k_name_specialty,0.5)*20+COALESCE(k_meaningful_specialty,0)*10+
                    COALESCE(k_phone_format,0.5)*15+COALESCE(k_year_valid,0.5)*10),1) >= 90 THEN 'A'
    WHEN ROUND(0.6*(c_coords+c_specialties+c_state+c_city+c_facility_type+c_capability+
                    c_procedure+c_zip+c_phone+c_description+c_contact)
             + 0.4*(COALESCE(k_coords_in_state,0.5)*25+COALESCE(k_zip_state,0.5)*20+
                    COALESCE(k_name_specialty,0.5)*20+COALESCE(k_meaningful_specialty,0)*10+
                    COALESCE(k_phone_format,0.5)*15+COALESCE(k_year_valid,0.5)*10),1) >= 75 THEN 'B'
    WHEN ROUND(0.6*(c_coords+c_specialties+c_state+c_city+c_facility_type+c_capability+
                    c_procedure+c_zip+c_phone+c_description+c_contact)
             + 0.4*(COALESCE(k_coords_in_state,0.5)*25+COALESCE(k_zip_state,0.5)*20+
                    COALESCE(k_name_specialty,0.5)*20+COALESCE(k_meaningful_specialty,0)*10+
                    COALESCE(k_phone_format,0.5)*15+COALESCE(k_year_valid,0.5)*10),1) >= 60 THEN 'C'
    ELSE 'D'
  END AS quality_tier
FROM scored;

═══════════════════════════════════════════
STEP 2 — COMPUTE SCORE SUMMARY
═══════════════════════════════════════════

Run this query and capture the result as score_summary:

SELECT
  COUNT(*) as total,
  SUM(CASE WHEN quality_tier = 'A' THEN 1 ELSE 0 END) as tier_A,
  SUM(CASE WHEN quality_tier = 'B' THEN 1 ELSE 0 END) as tier_B,
  SUM(CASE WHEN quality_tier = 'C' THEN 1 ELSE 0 END) as tier_C,
  SUM(CASE WHEN quality_tier = 'D' THEN 1 ELSE 0 END) as tier_D,
  ROUND(AVG(quality_score), 1) as avg_score,
  ROUND(AVG(completeness_score), 1) as avg_completeness,
  ROUND(AVG(consistency_score), 1) as avg_consistency,
  ROUND(AVG(CASE WHEN k_name_specialty = 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_name_spec_fail,
  ROUND(AVG(CASE WHEN k_zip_state = 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_zip_state_fail,
  ROUND(AVG(CASE WHEN k_coords_in_state = 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_coord_state_fail,
  ROUND(AVG(CASE WHEN k_meaningful_specialty = 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as pct_weak_specialty
FROM workspace.default.facilities_quality_scores;

═══════════════════════════════════════════
STEP 3 — SURFACE TIER C AND D RECORDS TO REVIEW QUEUE
═══════════════════════════════════════════

For every record with quality_tier IN ('C', 'D') that does NOT already have
a pending entry in facilities_review_queue with conflict_type = 'quality_score':

Call write_review_queue with:
  conflict_type:    'quality_score'
  unique_id:        the record's unique_id
  name:             the record's name
  existing_json:    JSON of the record from facilities_dedup
  incoming_json:    NULL  (not an ingestion conflict — this is a quality flag)
  diff_summary:     Build dynamically from failing checks. Example:
                    "Quality score: 55.1/100 (Tier D).
                     Failures: name contains 'Dental' but dentistry not in specialty list;
                     only familyMedicine as sole specialty."
  suggested_action: "(A) Add missing specialty tags to match facility name.
                     (B) Correct address_stateOrRegion or address_zipOrPostcode
                         if zip↔state mismatch is flagged.
                     (C) Dismiss — data is correct as-is (suppresses future alerts)."
  contact_hint:     source_urls or phone_numbers from the record, if present

═══════════════════════════════════════════
STEP 4 — SURFACE NAME↔SPECIALTY FAILURES IN TIER B
═══════════════════════════════════════════

For every record with quality_tier = 'B' AND k_name_specialty = 0 that does NOT
already have a pending 'quality_score' entry in facilities_review_queue:

Call write_review_queue with the same structure, but:
  diff_summary: "Quality score: [score]/100 (Tier B — name↔specialty mismatch).
                 Name implies [inferred specialty] but it is absent from specialty list."
  suggested_action: "(A) Add the missing specialty tag.
                     (B) Facility name is misleading — dismiss this alert."

═══════════════════════════════════════════
STEP 5 — RETURN SCORE SUMMARY
═══════════════════════════════════════════

Return score_summary JSON to the orchestrator.
```

### What the Databricks App Displays

The App reads two sources for the scoring dashboard:

**1. `facilities_quality_scores` view** — per-record scores, filterable by tier, state, or failing check:
- Quality overview dashboard: tier distribution, average score by state, trend vs prior run
- Drill-down: "Show all Tier B facilities in Maharashtra with name↔specialty failures"
- Per-record score card shown alongside the facility detail view

**2. `facilities_review_queue`** (conflict_type = 'quality_score') — quality flags appear in the same queue as dedup conflicts. The reviewer sees:
- Score and tier with plain-English explanation of which checks failed
- Suggested corrections as A/B/C choices
- Contact hint to verify with the facility directly
- Status changes (pending → resolved/dismissed) suppress the same flag on future runs

---

## 8. Ingestion Log Table Schema

```sql
CREATE TABLE IF NOT EXISTS workspace.default.facilities_ingestion_log (
  log_id       STRING  DEFAULT UUID(),
  logged_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  run_id       STRING,   -- ties all entries from one ingestion run together
  unique_id    STRING,
  name         STRING,
  action       STRING,   -- 'dropped' | 'updated' | 'inserted' | 'flagged' | 'geocoded' | 'coord_corrected' | 'field_cleaned'
  reason       STRING,   -- one of the log_reason codes used in agent prompts above
  detail       STRING    -- optional free text, e.g. "lat was -81.7 → corrected to 26.9"
)
USING DELTA;
```

---

## 9. Tool Definitions

All three sub-agents have access to the following tools. Implement each as a Python function registered with MLflow / Mosaic AI.

```python
def run_sql(statement: str) -> dict:
    """
    Execute a SQL statement against the Databricks SQL warehouse.
    Returns {"status": "ok", "rows": [...], "row_count": int}
    or {"status": "error", "message": str}.
    Uses warehouse_id from environment variable DATABRICKS_WAREHOUSE_ID.
    """

def nominatim_geocode(address: str) -> dict:
    """
    Geocode an address string using OpenStreetMap Nominatim.
    Returns {"lat": float, "lon": float, "display_name": str}
    or {"lat": None, "lon": None, "error": str}.

    Rules:
    - Enforces 1 request/second rate limit (use time.sleep(1) between calls)
    - Sets User-Agent: "VirtueFoundationIngestionAgent/1.0"
    - If result lat/lon is outside India bounds (lat 8-37, lon 68-98), returns error.
    """

def write_review_queue(rows: list) -> dict:
    """
    Insert one or more rows into workspace.default.facilities_review_queue.
    Each row is a dict with keys matching the table schema.
    Returns {"inserted": int}.
    """

def write_ingestion_log(rows: list) -> dict:
    """
    Append one or more rows to workspace.default.facilities_ingestion_log.
    Each row is a dict with keys: run_id, unique_id, name, action, reason, detail.
    Returns {"inserted": int}.
    """
```

---

## 10. Worked Examples from Prior Session

These are real cases encountered during the initial cleaning pass on the 10,088-row source dataset. Use these as ground truth for validating agent behavior.

---

### Example 1 — Scraper Corruption, Pattern A (text-as-rows)

**Situation:** The scraper parsed a university health centre's webpage and split the staff directory into individual rows, treating each text line as a separate facility.

```
Input unique_id:      "Dr. Anvita Verma | Assistant Professor (Social Work)  "
Input name:           ""
Input address_city:   NULL
Input latitude:       NULL

Trigger:  unique_id does NOT match UUID regex
          name is empty

Action:   DROP
Log:      { action: "dropped", reason: "scraper_corruption_pattern_a",
            detail: "unique_id is free text, not UUID; name is empty" }
```

Similar rows from the same scraper run:
```
unique_id: "Mobile: +91-9838602509  "                  → DROP
unique_id: "Email: verma_anvita@lkouniv.ac.in  "       → DROP
unique_id: "---|---  "                                  → DROP
unique_id: "Assistant Professor (Botany)  "             → DROP
```

**Total dropped from this pattern in initial pass: 79 records**

---

### Example 2 — Scraper Corruption, Pattern B (column shift)

**Situation:** A facility's JSON record was catastrophically misaligned. The scraper placed content from one field into the next, shifting everything left.

```
Input unique_id:            "For Instant Booking please call +91 7303555015"
Input name:                 '["gynecologyAndObstetrics","reproductiveEndocrinologyAndInfertility",
                              "familyMedicine","reproductiveEndocrinologyAndInfertility",...]'
Input address_city:         "kie"
Input address_zipOrPostcode: "13.026690483093262"   ← this is a latitude value, not a zip

Trigger:  name LIKE '[%'  (specialties array landed in name column)
          address_city = 'kie'  (column-shift marker — consistent across all 9 affected rows)

Action:   DROP
Log:      { action: "dropped", reason: "scraper_corruption_pattern_b",
            detail: "name contains specialties JSON array; city='kie' confirms column shift" }
```

**Total dropped from this pattern in initial pass: 9 records**

> **Note for agent implementers:** The value `'kie'` in `address_city` appeared in ALL 9 column-shift records and in no legitimate records. It likely originates from an HTTP cookie fragment parsed into the wrong field. Treat it as a reliable sentinel value.

---

### Example 3 — Type 2 Dedup: Same Name + Location, Worse Coordinates Removed

**Situation:** Two records for the same dental hospital existed with identical names but different GPS coordinates. Investigation showed one set of coordinates was 26.5km from the expected location; the other was 20.2km away (both had some GPS error, but one was clearly more accurate).

```
Record A: unique_id = 3e8946bd-04ac-4d8a-b921-90ee9153f5dd
          name      = "Siri Dental Hospital"
          city      = "New Delhi"
          latitude  = 28.4567,  longitude = 77.1234
          distance from Delhi city center: 26.5km  ← worse

Record B: unique_id = a1b2c3d4-...
          name      = "Siri Dental Hospital"
          city      = "New Delhi"
          latitude  = 28.6789,  longitude = 77.5678
          distance from Delhi city center: 20.2km  ← better

Action:   KEEP Record B, DROP Record A
Log:      { action: "dropped", reason: "type2_dedup_coord_quality",
            detail: "3e8946bd is 26.5km from city center vs 20.2km for kept record" }
Exclusion: 3e8946bd added to permanent exclusion list
```

---

### Example 4 — Missing Coordinates, Resolved via Pincode Directory

**Situation:** 19 records had valid 6-digit Indian PIN codes but no coordinates. The India Post pincode directory table provided post-office-level coordinates (1–5km accuracy).

```
Record: unique_id            = 12d987ef-...
        name                 = "Bharati Fertility Center"
        address_zipOrPostcode = "600028"
        latitude             = NULL
        longitude            = NULL

Step 1: SELECT AVG(TRY_CAST(latitude AS DOUBLE)), AVG(TRY_CAST(longitude AS DOUBLE))
        FROM india_post_pincode_directory
        WHERE pincode = 600028
        Result: lat = 13.05, lon = 80.449  (1 post office entry)

Step 2: 13.05 is within India bounds (8–37°N) ✓

Action: UPDATE latitude = 13.05, longitude = 80.449
Log:    { action: "geocoded", reason: "geocoded_via_pincode",
          detail: "zip 600028 → 1 post office entry in directory" }
```

**Other records resolved the same way in initial pass:**
```
Oberoi Hospital          (144001) → lat=31.328, lon=75.545  (12 post offices, avg)
Manorama Hospitex        (741201) → lat=23.155, lon=88.506  (12 post offices, avg)
Green Dental Care        (800001) → lat=25.590, lon=85.125  (18 post offices, avg)
Sanjeevani Ayurvedic     (250001) → lat=29.044, lon=77.748  (35 post offices, avg)
```

> **Implementation note:** Use `TRY_CAST(p.latitude AS DOUBLE)` not `CAST(...)` — the pincode directory contains `'NA'` string values in the latitude column that cause hard failures with plain CAST.

---

### Example 5 — Missing Coordinates, Resolved via Nominatim

**Situation:** Some records had no usable PIN code in the directory. Nominatim (OpenStreetMap) was queried with the address.

```
Record: name             = "Gynaecare Women's Hospital"
        address_line1    = "Ramdaspeth"
        address_city     = "Nagpur"
        address_stateOrRegion = "Maharashtra"
        address_zipOrPostcode = "411010"
        latitude         = NULL

Step 1: Pincode lookup on 411010 → 0 entries in directory (no match)

Step 2: Nominatim query:
        "Ramdaspeth, Nagpur, Maharashtra, India"
        GET https://nominatim.openstreetmap.org/search?q=...&format=json&limit=1
        User-Agent: VirtueFoundationIngestionAgent/1.0
        Result: lat=21.1366, lon=79.0750
        display_name: "Ramdaspeth, Nagpur City, Nagpur, Maharashtra, 411010, India"

Step 3: 21.1366 is within India bounds ✓

Action: UPDATE latitude = 21.1366, longitude = 79.0750
Log:    { action: "geocoded", reason: "geocoded_via_nominatim",
          detail: "query: 'Ramdaspeth, Nagpur, Maharashtra, India'" }
```

---

### Example 6 — Out-of-India Coordinates Corrected via Pincode

**Situation:** Six records had wildly incorrect coordinates — one was in Antarctica, one in Mongolia, one in the North Atlantic. All had valid Indian addresses that allowed correction.

```
Record: name                  = "Krishna Hospital Multispeciality"
        latitude              = -81.706  ← Antarctica / near South Pole
        longitude             =  26.953
        address_zipOrPostcode = "226021"
        address_city          = "Lucknow"
        address_stateOrRegion = "Uttar Pradesh"

Step 1: Detect: latitude -81.7 is NOT in range 8–37°N → outside India
Step 2: Pincode lookup on 226021 → lat=26.9077, lon=80.9503 (3 post offices)
Step 3: 26.9077 is within India bounds ✓

Action: UPDATE latitude=26.9077, longitude=80.9503
Log:    { action: "coord_corrected", reason: "coord_corrected_pincode",
          detail: "was lat=-81.71 lon=26.95 (outside India); corrected via zip 226021" }
```

**All six out-of-India corrections from initial pass:**
```
Cardia Health Care           (7.71°N, 109.69°E → S. China Sea)  zip 201305 → Noida coords
Cura Imaging & Gastro Clinic (2.95°N, 41.39°E → Somalia)        Nominatim  → Nagpur coords
Hzb Arogyam Hospital        (46.07°N, 106.17°E → Mongolia)       zip 825301 → Hazaribagh
Krishna Hospital             (-81.71°N, 26.95°E → Antarctica)    zip 226021 → Lucknow
Sanjivani Multi Speciality   (59.95°N, -38.26°E → N. Atlantic)  zip 690509 → Chengannur
The Family Tree Hospital     (32.96°N, 7.48°E → Algeria)         zip 517501 → Tirupati
```

---

### Example 7 — State Standardization (Representative Cases)

**Situation:** The `address_stateOrRegion` field contained 234 distinct raw values in the initial dataset. The canonical mapping reduced these to 35 values (28 states + 7 UTs).

```
Type: Alternate spelling
  'Tamilnadu'    → 'Tamil Nadu'
  'Orissa'       → 'Odisha'
  'Chattisgarh'  → 'Chhattisgarh'
  'Uttaranchal'  → 'Uttarakhand'
  'Madhyapradesh'→ 'Madhya Pradesh'
  'Telengana'    → 'Telangana'

Type: Abbreviation
  'Up','U.p','U.p.' → 'Uttar Pradesh'
  'Mh','Ms'         → 'Maharashtra'
  'Gj'              → 'Gujarat'
  'Ts'              → 'Telangana'
  'Dl','Nct'        → 'Delhi'
  'U.k.'            → 'Uttarakhand'

Type: City → state (most common)
  'Mumbai','Navi Mumbai','Thane','Pune','Nagpur' → 'Maharashtra'
  'Chennai','Salem','Erode','Cuddalore'          → 'Tamil Nadu'
  'Hyderabad'                                    → 'Telangana'
  'Kolkata','Hooghly','Howrah'                   → 'West Bengal'
  'Ahmedabad','Bhavnagar','Kutch'                → 'Gujarat'
  'New Delhi','West Delhi','South Delhi'         → 'Delhi'

Type: District → state
  'North 24 Parganas','South 24 Parganas'        → 'West Bengal'
  'Ernakulam','Malappuram','Kasaragod'            → 'Kerala'
  'Faridabad','Jhajjar'                           → 'Haryana'
  'Dakshin Kannad'                                → 'Karnataka'

Type: Compound / city+state string
  'Ghaziabad, Uttar Pradesh' → 'Uttar Pradesh'
  'Sirsa, Haryana'           → 'Haryana'
  'Kutch, Gujarat'           → 'Gujarat'
  'Jammu & Kashmir'          → 'Jammu and Kashmir'

Type: Unresolvable → NULL (6 values)
  'Green City','Central India','Sarna','New Mondha','Bigbara','Azad Nagar' → NULL
```

---

### Example 8 — Field-Type Cleaning

```
yearEstablished = "3000"
  → TRY_CAST("3000" AS INT) = 3000, NOT BETWEEN 1800 AND 2025
  → SET TO NULL
  Log: { reason: "invalid_year", detail: "value 3000 outside valid range" }

numberDoctors = "abc"
  → TRY_CAST("abc" AS DOUBLE) IS NULL
  → SET TO NULL
  Log: { reason: "invalid_numeric", detail: "non-numeric value in numberDoctors" }

equipment = '[]'
  → empty JSON array, no signal
  → SET TO NULL
  Log: { reason: "invalid_array_field", detail: "empty array []" }

equipment = '[""]'
  → single empty-string element; scraper artifact but not empty
  → KEEP as-is (no log entry)

specialties (before): '["internalMedicine","cardiology","internalMedicine",
  "internalMedicine","cardiology","internalMedicine","internalMedicine",...]'
  Raw count: 28 entries
specialties (after ARRAY_DISTINCT): '["internalMedicine","cardiology"]'
  Distinct count: 2
  Log: { reason: "field_cleaned", detail: "specialties deduplicated 28 → 2 distinct values" }
```

---

---

### Example 9 — Scoring Agent: Tier D flag surfaced to review queue

**Situation:** After ingestion, the scoring agent detects a dental clinic whose name implies dentistry but whose specialty list only contains `familyMedicine`.

```
Record: name = "Vasundhara Dental Clinic & Orthodontic Centre"
        address_stateOrRegion = "Delhi"
        address_zipOrPostcode = "201012"
        specialties = '["familyMedicine"]'
        quality_score = 55.4  →  Tier D

Failing checks:
  k_name_specialty = 0
    → name RLIKE '(dental|orthodont)' is TRUE
    → ARRAY_CONTAINS(spec_arr, 'dentistry') is FALSE
    → mismatch detected
  k_meaningful_specialty = 0
    → only 1 distinct specialty (familyMedicine)
  k_zip_state = 0
    → zip 201012 is in Ghaziabad, Uttar Pradesh per pincode directory
    → stated state is Delhi  →  mismatch

write_review_queue called with:
  conflict_type:    'quality_score'
  name:             "Vasundhara Dental Clinic & Orthodontic Centre"
  diff_summary:     "Quality score: 55.4/100 (Tier D).
                     Failures:
                     (1) Name contains 'Dental' and 'Orthodontic' but specialty
                         list does not include dentistry or orthodontics —
                         only familyMedicine is tagged.
                     (2) ZIP 201012 belongs to Ghaziabad, Uttar Pradesh per
                         India Post directory but address_stateOrRegion = Delhi."
  suggested_action: "(A) Add dentistry and orthodontics to specialty list;
                         correct state to Uttar Pradesh if facility is in Ghaziabad.
                     (B) Dismiss — data is correct as-is."
  contact_hint:     [phone_numbers or source_urls from record]
```

---

### Example 10 — Scoring Agent: Tier B name↔specialty flag

**Situation:** A cardiac hospital scores 86.2 (Tier B) because cardiology is absent from its specialty list despite appearing in the facility name.

```
Record: name = "Fortis Cardiac and Multispeciality Hospital"
        specialties (after ARRAY_DISTINCT) = ["internalMedicine","generalSurgery",
                                               "orthopedicSurgery","familyMedicine"]
        quality_score = 86.2  →  Tier B

Failing check:
  k_name_specialty = 0
    → name RLIKE '(cardiac|cardio|heart)' is TRUE
    → ARRAY_CONTAINS(spec_arr, 'cardiology') is FALSE

write_review_queue called with:
  conflict_type:    'quality_score'
  diff_summary:     "Quality score: 86.2/100 (Tier B — name↔specialty mismatch only).
                     Name contains 'Cardiac' but cardiology is not in the specialty list.
                     Current specialties: internalMedicine, generalSurgery,
                     orthopedicSurgery, familyMedicine."
  suggested_action: "(A) Add cardiology to the specialty list — this is likely
                         a tagging omission by the scraper.
                     (B) Dismiss — the facility no longer offers cardiac services."
  contact_hint:     [source_urls or phone_numbers]
```

---

### Example 11 — Scoring Agent: run summary logged

**Situation:** After a batch of 150 new records was ingested, the scoring agent re-scores the full table and appends a summary to the ingestion log.

```
score_summary returned to orchestrator:
{
  "total": 10138,
  "tier_A": 8571,       -- up from 8438 (new records skewed high quality)
  "tier_B": 1516,
  "tier_C": 45,
  "tier_D": 6,
  "avg_score": 91.8,    -- up 0.1 from baseline 91.7
  "avg_completeness": 89.9,
  "avg_consistency": 95.1,
  "pct_name_spec_fail": 9.1,
  "pct_zip_state_fail": 1.5,
  "pct_coord_state_fail": 1.2,
  "pct_weak_specialty": 2.5
}

Orchestrator writes to facilities_ingestion_log:
  action: "score_run_complete"
  detail: "avg_score=91.8 tier_A=8571 tier_B=1516 tier_C=45 tier_D=6
           new_quality_flags_queued=3"
```

---

## 11. Matching Guidance for Downstream Consumers

When querying `facilities_dedup` to match a patient to a hospital:

1. **Always use `ARRAY_DISTINCT`** on specialties even after ingestion — new batches may add repetition:
   ```sql
   WHERE ARRAY_CONTAINS(ARRAY_DISTINCT(FROM_JSON(specialties, 'ARRAY<STRING>')), 'cardiology')
   ```

2. **Deprioritize `internalMedicine` and `familyMedicine`** as primary signals — they appear in 68% and 52% of all facilities respectively and function as catch-alls. Use them only as a fallback tier when no more specific specialty matches exist.

3. **Geographic precision varies by record:**
   - ~92% of records have facility-level GPS coordinates (scraper-sourced)
   - ~8% have pincode-level coordinates (post-office centroid, accuracy ~1–5km)
   - The `geocoded_via_pincode` and `geocoded_via_nominatim` log entries identify which records were approximated

4. **Northeast India coverage is sparse:** Mizoram (3), Arunachal Pradesh (3), Nagaland (6). Distance-based matching may return results 100km+ away for patients in these states. Consider surfacing a coverage warning in the app for these states.
