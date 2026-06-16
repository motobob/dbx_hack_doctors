# NFHS-5 Survey Ingestion Data Quality: Requirements & Baseline

**Dataset:** `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators`

**Clean output:** `workspace.default.nfhs_district_indicators_clean`

**Quality flag output:** `workspace.default.nfhs_indicator_quality_flags`

**Ingestion scope:** parse, normalize, and quality-flag district survey indicators.

**Out of scope:** downstream district risk scoring, care-gap scoring, medical desert ranking, and facility coverage recommendations.

**Profiled locally:** June 2026

**Records processed:** 706 district rows

---

## 1. Source Data Overview

The NFHS-5 District Health Indicators table contains district-level survey indicators from India's National Family Health Survey 2019-21 district fact sheets. It is a demand-side public health context table, not a facility, provider, or postal geography table.

The source grain is:

```text
one row = one district within one state or union territory
```

This table should be used as a clean survey/context input after ingestion. It should not be treated as live operational data, exact current population health status, or a direct source of facility supply.

**Important distinction:** this ingestion document only defines data-quality preparation for the survey table. It does not define downstream risk scoring logic.

---

## 2. Source Schema Summary

The local table has:

| Metric | Count |
|---|---:|
| Source rows | 706 |
| Columns | 109 |
| Distinct state/UT labels | 36 |
| Distinct state/district keys | 706 |

Core geography columns:

| Field | Type | Notes |
|---|---|---|
| `district_name` | STRING | District label; contains trailing whitespace in some rows |
| `state_ut` | STRING | State or union territory label |

Survey base columns:

| Field | Type | Notes |
|---|---|---|
| `households_surveyed` | DOUBLE | Survey base count |
| `women_15_49_interviewed` | DOUBLE | Survey base count |
| `men_15_54_interviewed` | DOUBLE | Survey base count |

The remaining columns are district-level indicators covering household conditions, maternal and reproductive health, child health, vaccination, nutrition, anaemia, non-communicable diseases, cancer screening, tobacco, and alcohol.

---

## 3. Baseline Data Quality Profile

### 3.1 Row Grain and Keys

| Check | Result |
|---|---:|
| Rows | 706 |
| Distinct `(state_ut, district_name)` keys after trim/lowercase | 706 |
| Duplicate district keys detected locally | 0 |
| Blank cells detected locally | 0 |

The table appears structurally complete at the row/key level. The main quality issues are inside indicator values.

### 3.2 Survey Value Caveats

| Caveat | Count |
|---|---:|
| Suppressed/unavailable `*` cells | 4,125 |
| Parenthesized estimate cells | 5,068 |
| Columns with non-plain numeric values | 49 |

Interpretation:

- `*` means the indicator is suppressed, unavailable, or not reliable enough to publish. Treat as NULL, never zero.
- Parenthesized values such as `(29.5)` are numeric estimates with a caution flag, commonly indicating a smaller unweighted sample base.
- Numeric-looking columns may be typed as string because of suppression markers, parentheses, and whitespace.

### 3.3 High-Suppression Columns

The columns with the most `*` values include:

| Column | Suppressed cells |
|---|---:|
| `non_breastfeeding_child_6_23m_receiving_an_adequate_diet16_pct` | 643 |
| `child_6_8m_receiving_solid_or_semi_solid_food_and_breastmil_pct` | 642 |
| `children_with_diarrhoea_2wk_who_received_zinc_child_u5_pct` | 492 |
| `children_with_diarrhoea_2wk_who_received_oral_rehydration_s_pct` | 492 |
| `children_with_diarrhoea_2wk_taken_to_a_health_facility_or_h_pct` | 492 |
| `children_born_at_home_who_were_taken_to_a_health_facility_f_pct` | 422 |
| `child_u6m_exclusively_breastfed_pct` | 261 |
| `children_with_fever_or_symptoms_of_ari_2wk_taken_to_a_healt_pct` | 224 |
| `births_in_a_private_fac_that_were_delivered_by_csection_5y_pct` | 150 |
| `pregnant_w15_49_who_are_anaemic_lt_11_0_g_dl_22_pct` | 134 |

### 3.4 High-Caution Columns

The columns with the most parenthesized estimates include:

| Column | Parenthesized cells |
|---|---:|
| `pregnant_w15_49_who_are_anaemic_lt_11_0_g_dl_22_pct` | 421 |
| `child_u6m_exclusively_breastfed_pct` | 347 |
| `child_12_23m_fully_vaccinated_based_on_information_from_vax_pct` | 323 |
| `children_with_fever_or_symptoms_of_ari_2wk_taken_to_a_healt_pct` | 264 |
| `child_12_23m_who_received_most_of_their_vaccinations_in_a_p_pct` | 252 |
| `child_12_23m_who_received_most_of_their_vaccinations_in_a_2_pct` | 252 |
| `child_24_35m_who_have_received_a_second_dose_of_mcv_mcv_pct` | 232 |
| `child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct` | 232 |
| `child_12_23m_who_have_received_bcg_pct` | 232 |
| `child_12_23m_who_have_received_3_doses_of_rotavirus_vaccine_pct` | 232 |

---

## 4. Cleaning Rules

### 4.1 Geography Normalization

**Rule G1 - Preserve raw geography**

Always retain:

- `state_ut_raw`
- `district_name_raw`

**Rule G2 - Trim labels**

Apply trim and whitespace collapse to:

- `state_ut`
- `district_name`

Some district names have trailing whitespace, for example `South Andaman ` and `Srikakulam `.

**Rule G3 - Create join keys**

Create:

```text
state_ut_norm
district_name_norm
district_join_key
```

Recommended transformations:

- lowercase
- trim
- collapse whitespace
- normalize ampersands to `and`
- remove punctuation from join key only
- preserve raw and display values for audit

**Rule G4 - Do not silently reconcile district boundary changes**

NFHS-5 uses 2019-21 district fact-sheet geography. Do not assume it matches current administrative boundaries or facility/PIN district labels. Boundary mismatches should be flagged for join review.

### 4.2 Indicator Parsing

**Rule V1 - Plain numeric value**

If value is plain numeric:

```text
92.2 -> indicator_value = 92.2
```

Set:

```text
is_suppressed = false
is_caution_estimate = false
parse_status = 'parsed_numeric'
```

**Rule V2 - Suppressed value**

If value is exactly `*` after trim:

```text
indicator_value = NULL
```

Set:

```text
is_suppressed = true
is_caution_estimate = false
parse_status = 'suppressed'
```

Do not convert `*` to zero.

**Rule V3 - Parenthesized estimate**

If value matches a parenthesized numeric pattern such as `(29.5)`:

```text
indicator_value = 29.5
```

Set:

```text
is_suppressed = false
is_caution_estimate = true
parse_status = 'parsed_caution_estimate'
```

Parentheses should not be discarded without preserving the caution metadata.

**Rule V4 - Whitespace numeric**

If value has leading/trailing spaces around a number:

```text
"83.2 " -> indicator_value = 83.2
```

Set:

```text
parse_status = 'parsed_numeric_trimmed'
```

**Rule V5 - Parse failure**

If value is not numeric, `*`, or parenthesized numeric:

```text
indicator_value = NULL
parse_status = 'parse_failed'
```

Write a row to `nfhs_indicator_quality_flags`.

### 4.3 Value Range Checks

Most `_pct` columns should be between 0 and 100.

**Rule R1 - Percentage bounds**

If a parsed `_pct` indicator is outside `[0, 100]`:

- retain raw value
- set parsed value to NULL
- flag `pct_out_of_range`

**Rule R2 - Count fields**

Survey base fields should be non-negative:

- `households_surveyed`
- `women_15_49_interviewed`
- `men_15_54_interviewed`

If negative or non-numeric:

- set parsed value to NULL
- flag `invalid_survey_base_count`

**Rule R3 - Currency-like field**

`average_out_of_pocket_expenditure_per_delivery_in_a_public_fac` is not a percentage. Do not apply a 0-100 range check.

### 4.4 Type Normalization

Create numeric parsed versions for all indicator columns, including columns currently typed as STRING.

Recommended output pattern:

```text
<indicator_name>_value
<indicator_name>_suppressed
<indicator_name>_caution
<indicator_name>_parse_status
```

For a wide table MVP, it is acceptable to keep one numeric cleaned column per indicator and move flags into the long-form quality table.

---

## 5. Recommended Output Tables

### 5.1 Clean Wide Table

`workspace.default.nfhs_district_indicators_clean`

One row per district/state pair.

Required fields:

```text
state_ut_raw
district_name_raw
state_ut_norm
district_name_norm
district_join_key
survey_period
source_name
source_table
households_surveyed
women_15_49_interviewed
men_15_54_interviewed
<parsed indicator numeric columns>
suppressed_cell_count
caution_cell_count
parse_failed_cell_count
row_quality_tier
cleaned_at
```

### 5.2 Long Quality Flag Table

`workspace.default.nfhs_indicator_quality_flags`

One row per district/indicator quality condition.

Required fields:

```text
flag_id
state_ut_norm
district_name_norm
district_join_key
indicator_name
raw_value
parsed_value
flag_type
severity
explanation
source_period
created_at
```

Suggested `flag_type` values:

```text
suppressed_value
caution_estimate
parse_failed
pct_out_of_range
invalid_survey_base_count
geography_join_warning
```

---

## 6. Row Quality Tier

The row quality tier describes ingestion confidence for the survey row. It is not a health risk score.

| Tier | Meaning |
|---|---|
| A | Geography key is clean; low suppression/caution burden |
| B | Geography key is clean; moderate suppression or caution burden |
| C | Geography key is usable but many indicators are suppressed or caution-estimated |
| D | Geography key problem or parse failures that make the row unsafe for automated joins |

Suggested row quality score:

```text
nfhs_ingestion_quality_score =
  0.30 * geography_key_quality
+0.25 * parse_success_rate
+0.20 * suppression_completeness
+0.15 * caution_burden_score
+0.10 * survey_base_validity
```

This score should only describe ingestion quality. Do not use it as a district health risk score.

---

## 7. Join Guidance

NFHS should join downstream by normalized state/district keys only after geography normalization.

Recommended join fields:

```text
state_ut_norm
district_name_norm
district_join_key
```

Do not directly join raw district labels to facilities or PIN tables without normalization and ambiguity checks.

Recommended precedence for facility geography:

1. Valid facility coordinates with administrative boundary polygons.
2. Facility's cleaned state/district fields.
3. PIN lookup with confidence flags.
4. NFHS district join only after district identity is established.

NFHS does not identify facilities. It should not be used to correct facility names, coordinates, or dedupe clusters.

---

## 8. Non-Goals

This ingestion process does not:

- rank districts by medical desert risk
- compute care-gap scores
- recommend facility placement
- measure service availability
- infer facility quality
- resolve facility duplicates
- geocode facilities
- decide which districts are underserved

Those are downstream analytics or app-layer tasks that may consume this cleaned survey table later.

---

## 9. Demo Language

Good phrasing:

- "NFHS-5 is our district-level survey context table."
- "The ingestion agent preserves suppression and caution flags instead of flattening survey caveats away."
- "A parenthesized value is parsed as numeric but marked lower confidence."
- "Suppressed values become NULL, not zero."
- "This table is cleaned for downstream use, but this document does not define downstream risk scoring."

Avoid saying:

- "NFHS tells us where facilities are missing."
- "Suppressed survey values mean zero."
- "Parenthesized estimates are equivalent to regular estimates."
- "This ingestion score is the same as district health risk."
