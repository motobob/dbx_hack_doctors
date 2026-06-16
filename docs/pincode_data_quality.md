# India Post PIN Code Directory Data Quality: Requirements & Baseline

**Dataset:** `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory`

**Clean output:** `workspace.default.pincode_lookup_clean`

**Ambiguity output:** `workspace.default.pincode_ambiguity_flags`

**Profiled locally:** June 2026

**Records processed:** 165,627 source rows

---

## 1. Source Data Overview

The India Post PIN Code Directory is a public postal geography lookup table. It contains one row per post office, not one row per PIN code. This distinction is critical: a single six-digit PIN can appear on many rows and can map to multiple offices, districts, divisions, regions, and in some cases states.

This table is useful for enriching healthcare facility records with postal geography and approximate coordinates, but it should not be treated as exact facility geocoding.

**Schema:**

| Field | Type | Notes |
|---|---|---|
| `circlename` | STRING | Postal circle, usually state-like administrative grouping |
| `regionname` | STRING | Postal region; contains `NA` for 315 rows |
| `divisionname` | STRING | Postal division |
| `officename` | STRING | Post office name; row grain is post office |
| `pincode` | BIGINT | Six-digit Indian PIN code |
| `officetype` | STRING | `BO`, `PO`, or `HO` |
| `delivery` | STRING | `Delivery` or `Non Delivery` |
| `district` | STRING | District label; contains `NA` for 715 rows |
| `statename` | STRING | State/UT label; contains `NA` for 715 rows |
| `latitude` | STRING | Stored as string; contains `NA`, malformed values, and swapped coordinates |
| `longitude` | STRING | Stored as string; contains `NA`, malformed values, and swapped coordinates |

---

## 2. Baseline Profile

### 2.1 Table Shape

| Metric | Count |
|---|---:|
| Source rows | 165,627 |
| Columns | 11 |
| Unique PIN codes | 19,586 |
| Exact duplicate rows | 2 |
| Invalid PIN formats | 0 |
| Distinct district labels | 750 |
| Distinct state labels, including `NA` | 37 |

### 2.2 Office Type Distribution

| Office type | Rows |
|---|---:|
| `BO` | 140,270 |
| `PO` | 24,546 |
| `HO` | 811 |

### 2.3 Delivery Distribution

| Delivery status | Rows |
|---|---:|
| `Delivery` | 157,901 |
| `Non Delivery` | 7,726 |

### 2.4 Missing or Invalid Location Fields

| Issue | Rows |
|---|---:|
| `regionname = 'NA'` | 315 |
| `district = 'NA'` | 715 |
| `statename = 'NA'` | 715 |
| Both district and state are `NA` | 715 |
| Latitude/longitude missing or `NA` | 12,009 |
| Coordinate strings fail numeric parsing | 6 |
| Numeric coordinates outside India bounds | 2,613 |
| Candidate swapped lat/lon values | 791 |
| Latitude equals longitude | 730 |

India bounding box used for validation:

| Coordinate | Accepted range |
|---|---|
| Latitude | 8 to 37 |
| Longitude | 68 to 98 |

### 2.5 PIN Cardinality and Ambiguity

The table is post-office grain, not PIN grain.

| Metric | Count |
|---|---:|
| Median rows per PIN | 7 |
| 95th percentile rows per PIN | 21 |
| Maximum rows for one PIN | 153 |
| PINs mapping to multiple states | 290 |
| PINs mapping to multiple districts | 1,478 |
| PINs mapping to multiple regions | 77 |
| PINs mapping to multiple divisions | 129 |
| PINs mapping to multiple postal circles | 17 |
| PINs with multiple office types | 16,763 |
| PINs with both delivery and non-delivery offices | 3,349 |

Example multi-state PIN:

| PIN | States | Districts |
|---|---|---|
| `506003` | `ANDHRA PRADESH`, `TELANGANA` | `Bapatla`, `HANUMAKONDA` |

Example multi-district PIN:

| PIN | State | Districts |
|---|---|---|
| `504273` | `TELANGANA` | `KUMURAM BHEEM ASIFABAD`, `MANCHERIAL` |

---

## 3. Cleaning Rules

### 3.1 Structural Checks

**Rule S1 - Drop exact duplicate rows**

- Detection: all 11 source fields are identical.
- Action: keep one copy.
- Baseline: 2 exact duplicate rows detected.

**Rule S2 - Validate PIN code format**

- Condition: `pincode` must be castable to a six-digit string matching `^[0-9]{6}$`.
- Action: rows with invalid PIN values are flagged for review and excluded from the PIN-level lookup.
- Baseline: no invalid PIN formats found locally.

**Rule S3 - Preserve post-office grain**

- Do not collapse source rows into one row per PIN without an explicit aggregation rule.
- Keep a cleaned post-office table and a separate PIN-level aggregate table.
- Every PIN-level output must include row count and ambiguity flags.

### 3.2 Text Normalization

**Rule T1 - Trim and normalize whitespace**

- Apply to all text fields.
- Collapse repeated spaces.
- Convert empty strings and `NA` sentinels to NULL where the field represents geography or coordinates.

**Rule T2 - Normalize state labels**

- Convert `statename` to a canonical state/UT display value.
- Source values are mostly uppercase. Convert known official values to title case, for example:
  - `TELANGANA` -> `Telangana`
  - `UTTAR PRADESH` -> `Uttar Pradesh`
  - `ANDAMAN & NICOBAR ISLANDS` -> `Andaman and Nicobar Islands`
  - `DADRA AND NAGAR HAVELI AND DAMAN AND DIU` -> `Dadra and Nagar Haveli and Daman and Diu`
- If `statename = 'NA'`, set canonical state to NULL and flag `missing_state`.

**Rule T3 - Preserve raw district labels while adding normalized join keys**

- Keep the original `district` value.
- Create `district_norm` using lowercase, trim, punctuation normalization, and whitespace collapse.
- Do not force district labels into a canonical map unless backed by a controlled district reference table.
- If `district = 'NA'`, set `district_norm` to NULL and flag `missing_district`.

**Rule T4 - Normalize office type and delivery**

- `officetype` must be one of `BO`, `PO`, `HO`.
- `delivery` must be one of `Delivery`, `Non Delivery`.
- Unknown values should be retained in the cleaned post-office table but flagged.

### 3.3 Coordinate Cleaning

**Rule C1 - Parse decimal coordinates**

- Convert latitude and longitude to doubles where possible.
- Treat `NA`, empty string, and NULL as missing.
- Some coordinate strings contain degree symbols or embedded spaces. Examples:
  - `17 deg 57'17.7`
  - `28.430354 deg N`
  - `28.4 32628`
  - `25.43 N`
- For MVP, flag these as `coord_parse_failed`.
- Stretch: parse degree and directional suffix values when unambiguous.

**Rule C2 - Validate India bounds**

- Accept coordinates only if latitude is between 8 and 37 and longitude is between 68 and 98.
- If numeric values are outside this range, flag `coord_outside_india`.

**Rule C3 - Correct likely swapped coordinates**

- If latitude is outside the latitude range but longitude is in the latitude range, and swapping creates a coordinate within India bounds, swap values.
- Flag the correction as `coord_swapped`.
- Baseline: 791 candidate swapped coordinate rows detected.

**Rule C4 - Flag suspicious equal coordinates**

- If latitude equals longitude, flag `coord_lat_equals_lon`.
- Do not auto-correct unless an independent source validates the location.
- Baseline: 730 rows detected.

**Rule C5 - Estimate PIN centroid with caution**

- For PIN-level lookup, compute a centroid from valid post-office coordinates only.
- Exclude missing, parse-failed, out-of-bounds, and uncorrected suspicious coordinates.
- Include:
  - `valid_coord_count`
  - `missing_coord_count`
  - `invalid_coord_count`
  - `centroid_confidence`
  - `max_coord_span_km_rough`
- If coordinate spread is large, flag `pin_coordinate_dispersion`.

### 3.4 PIN-Level Aggregation

Because one PIN can map to many post offices, the cleaned output should have two grains:

1. `pincode_post_offices_clean`: one row per post office.
2. `pincode_lookup_clean`: one row per PIN with aggregate geography and confidence.

**PIN-level aggregation fields:**

| Field | Description |
|---|---|
| `pincode` | Six-digit PIN |
| `post_office_count` | Number of source rows for the PIN |
| `canonical_state` | State if exactly one state is present, otherwise NULL |
| `state_count` | Number of distinct non-null states |
| `district_count` | Number of distinct non-null districts |
| `primary_district` | Most frequent district only when unambiguous enough |
| `primary_district_share` | Share of rows represented by primary district |
| `latitude_centroid` | Average valid latitude after corrections |
| `longitude_centroid` | Average valid longitude after corrections |
| `valid_coord_count` | Count of valid coordinate rows |
| `has_multi_state` | Boolean |
| `has_multi_district` | Boolean |
| `has_missing_geo` | Boolean |
| `pin_confidence_tier` | `A`, `B`, `C`, or `D` |

### 3.5 Ambiguity Rules

**Rule A1 - Multi-state PIN**

- Condition: one PIN maps to more than one non-null `statename`.
- Action: flag `multi_state_pin`.
- Do not use this PIN to assign a facility to a single state without additional evidence.

**Rule A2 - Multi-district PIN**

- Condition: one PIN maps to more than one non-null `district`.
- Action: flag `multi_district_pin`.
- Facility joins on this PIN should show ambiguity rather than picking a district silently.

**Rule A3 - Weak primary district**

- Condition: a PIN has multiple districts and the most frequent district accounts for less than 70 percent of rows.
- Action: set `primary_district` to NULL and flag `weak_primary_district`.

**Rule A4 - Missing district/state**

- Condition: district or state is NULL after sentinel handling.
- Action: retain row, but exclude from confident PIN-to-admin assignment.

---

## 4. Confidence Scoring

### 4.1 Post-Office Row Quality Score

Recommended row-level score:

```text
0.25 valid_pincode
+0.20 valid_state
+0.15 valid_district
+0.15 valid_coordinate
+0.10 valid_office_type
+0.10 valid_delivery_status
+0.05 valid_postal_hierarchy
```

Where:

- `valid_pincode`: six-digit PIN present.
- `valid_state`: canonical state present.
- `valid_district`: district present and not `NA`.
- `valid_coordinate`: parsed coordinate within India bounds after allowed swap correction.
- `valid_office_type`: office type in `BO`, `PO`, `HO`.
- `valid_delivery_status`: delivery in expected enum.
- `valid_postal_hierarchy`: circle, region, and division usable.

### 4.2 PIN-Level Confidence Tier

| Tier | Meaning | Suggested condition |
|---|---|---|
| A | Strong lookup | One state, one district, valid centroid, no major flags |
| B | Usable with caveat | One state, multiple districts but strong primary district, valid centroid |
| C | Ambiguous | Multi-district, missing centroid, or weak primary district |
| D | Unsafe for automatic assignment | Multi-state, missing state, invalid PIN, or severe coordinate conflict |

Facility enrichment should use:

- Tier A for automatic district/state enrichment.
- Tier B with visible caveat.
- Tier C for review or broad geography only.
- Tier D only as weak evidence, not an assignment.

---

## 5. Recommended Join Rules for Facilities

### Rule J1 - Never fan out facility rows by joining directly to post-office grain

Bad pattern:

```sql
SELECT *
FROM facilities f
JOIN india_post_pincode_directory p
  ON TRY_CAST(f.address_zipOrPostcode AS BIGINT) = p.pincode
```

This can multiply facility rows because one PIN maps to many post offices.

### Rule J2 - Join facilities to the PIN-level lookup

Preferred pattern:

```sql
SELECT
  f.*,
  p.canonical_state AS pincode_state,
  p.primary_district AS pincode_district,
  p.pin_confidence_tier,
  p.has_multi_state,
  p.has_multi_district
FROM facilities_clean f
LEFT JOIN pincode_lookup_clean p
  ON LPAD(CAST(f.address_zipOrPostcode AS STRING), 6, '0') = p.pincode
```

### Rule J3 - Do not override stronger facility evidence

If a facility has valid coordinates, spatial joins against district boundaries should outrank PIN-derived district assignment.

Suggested precedence:

1. Valid facility latitude/longitude plus boundary polygon.
2. Facility state/district fields after canonical cleaning.
3. Tier A or B PIN lookup.
4. Nominatim or other geocoder result, with rate limit and cache.
5. Human review.

### Rule J4 - Always expose join confidence

Any facility enriched from PIN code should carry:

- `location_source = 'pincode_directory'`
- `location_confidence`
- `pincode_ambiguity_flags`
- `post_office_count`
- `state_count`
- `district_count`

---

## 6. Review Queue Conditions

Rows or PINs should be surfaced for human review when:

- A PIN maps to multiple states.
- A PIN maps to multiple districts and no strong primary district exists.
- Coordinates are outside India and cannot be corrected by swapping.
- Latitude equals longitude.
- District or state is missing.
- Coordinate spread within a PIN is very large.
- Office type or delivery status is outside the expected enum.
- A facility join would change a facility's state/district from a stronger source.

---

## 7. Demo and Product Notes

The PIN directory should be framed as a geography assist layer, not a truth layer.

Good demo language:

- "A PIN code is not a district key."
- "The app prevents row fan-out by using a one-row-per-PIN lookup."
- "Ambiguous PINs are visible to reviewers and downstream planners."
- "PIN-derived coordinates are approximate postal centroids, not facility coordinates."

Avoid saying:

- "We geocoded facilities exactly by PIN."
- "Every PIN belongs to one district."
- "Postal centroid equals facility location."

---

## 8. Immediate Implementation Steps

1. Create `pincode_post_offices_clean` from the raw table with trimmed text, sentinel handling, coordinate parsing, and swap correction.
2. Create `pincode_lookup_clean` as a PIN-level aggregate.
3. Create `pincode_ambiguity_flags` for multi-state, multi-district, missing geography, and coordinate quality issues.
4. Add join-safe facility enrichment against `pincode_lookup_clean`, not the raw post-office table.
5. Surface PIN ambiguity in the Data Readiness Desk review queue.
