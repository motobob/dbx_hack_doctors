# Agent-Driven Workflow Pipeline v2

**Databricks Hackathon**  
**Healthcare Data Quality**  
**10 agents · trust-first scoring · human review at ambiguous decision points**

## One-Line Story

Ten agents work in sequence to profile, ingest, normalize, deduplicate, verify, geolocate, and score healthcare facility records, producing a facility trust layer that can safely feed medical desert planning.

## Core Shift in v2

The pipeline no longer treats populated fields as trustworthy by default.

`row_scorer_v2` scores each facility row by asking:

```text
Is this row coherent, evidenced, geospatially plausible, non-duplicative, and safe to count in planning?
```

This is a trust model, not a completeness model.

---

# Agent Pipeline

## Agent 01 - Ingestion Manager Agent

**Purpose**

- Accept incoming facility batches.
- Detect schema alignment issues and suspicious column shifts.
- Route new rows into the agent workflow without modifying trusted state directly.

**Outputs**

- Ingestion route.
- Schema alignment flags.
- Incoming row quality flags.

**Review triggers**

- Missing required identity/location fields.
- Column-shift signals.
- Uploaded rows that cannot be mapped to the canonical facility schema.

---

## Agent 02 - QA Profile Agent

**Purpose**

- Scan field groups for completeness and sparsity.
- Identify suspicious metadata.
- Produce dataset-level quality indicators.

**Outputs**

- Field group scores.
- Sparse group flags.
- Metadata validity flags.

**Review triggers**

- Sparse identity, location, capability, provenance, or metadata groups.
- Impossible years or nonnumeric planning fields.

---

## Agent 03 - PIN Code Ingestion Agent

**Purpose**

- Convert the raw India Post PIN directory into a safe enrichment layer.
- Preserve post-office grain while producing a one-row-per-PIN lookup.
- Surface postcode ambiguity before facility joins.

**Outputs**

- Clean post-office rows.
- PIN-level lookup.
- PIN ambiguity flags.
- PIN confidence tier.

**Review triggers**

- PIN maps to multiple states.
- PIN maps to multiple districts with weak primary district.
- Missing or invalid postal coordinates.
- Facility geography conflicts with PIN-derived geography.

---

## Agent 04 - NFHS Survey Ingestion Agent

**Purpose**

- Prepare NFHS-5 district survey indicators for reliable downstream context.
- Parse survey caveats without flattening them away.
- Normalize state/district join keys.

**Outputs**

- Clean district survey table.
- Indicator quality flags.
- Survey ingestion quality tier.

**Review triggers**

- Duplicate or unmappable district keys.
- Suppressed values in important indicators.
- Parenthesized caution estimates.
- Parse failures in survey fields.

**Important**

This agent does not compute medical desert risk. It only prepares survey context for later analysis.

---

## Agent 05 - Deduplication Agent

**Purpose**

- Cluster exact and near-duplicate facility records.
- Compare facility name, address, city, state, postcode, coordinates, and source overlap.
- Recommend merges only when confidence is strong.

**Outputs**

- Duplicate cluster IDs.
- Merge recommendations.
- Certain vs possible duplicate labels.

**Review triggers**

- Borderline duplicate clusters.
- Same name and city but conflicting coordinates.
- Incoming rows that may replace or remove existing evidence.

---

## Agent 06 - Evidence / Claim Verification Agent

**Purpose**

- Inspect descriptions, specialties, capabilities, procedures, equipment, and source references.
- Extract evidence for planning-critical claims.
- Classify claims by evidence strength.

**Outputs**

- Claim-level trust status.
- Capability evidence rows.
- Contradiction flags.
- Review-required claim list.

**Capability focus**

- ICU
- NICU
- Emergency
- Maternity
- Trauma
- Oncology
- Dialysis
- Surgery

**Review triggers**

- Weak clinical claims.
- Claims supported only by generic text.
- Structured fields and free text disagree.
- High-impact claims with no equipment or procedure support.

---

## Agent 07 - Geolocation / Coverage Agent

**Purpose**

- Validate latitude/longitude against India bounds.
- Check location completeness.
- Flag suspicious or borderline geocodes.
- Prepare facility records for regional aggregation.

**Outputs**

- Geocode quality score.
- Flagged geocode records.
- Coverage gap signals.

**Review triggers**

- Missing coordinates.
- Coordinates outside India.
- Likely swapped coordinates.
- Location fields that cannot support planning geography.

---

## Agent 08 - Shortage Agent

**Purpose**

- Identify areas where facility capability evidence appears sparse.
- Separate possible care gaps from data-poor regions.
- Prepare planning signals for risk synthesis.

**Outputs**

- Shortage areas.
- Capability gap list.
- Data-confidence label.

**Review triggers**

- Low facility capability evidence by geography.
- Regions that look underserved only because source data is sparse.
- Capability gaps that depend on weak or unreviewed claims.

---

## Agent 09 - Human Review Gate Agent

**Purpose**

- Convert agent uncertainty into proof/reject work.
- Escalate ambiguous findings to human reviewers.
- Protect planning outputs from unreviewed material uncertainty.

**Outputs**

- Review queue.
- Severity labels.
- Material planning impact score.

**Auto-handled by agents**

- Exact duplicates with strong evidence.
- Clearly malformed fields.
- Deterministic location fixes.
- Clear evidence for a claim.
- Clear lack of evidence.

**Escalated to humans**

- Borderline duplicate clusters.
- Contradictory claim evidence.
- Mixed specialty signals.
- Ambiguous geocodes or postcode mismatches.
- Claims supported only by weak text.
- Records where confidence materially changes planning output.

---

## Agent 10 - Risk / Coverage Scoring Agent

**Purpose**

- Synthesize upstream quality, evidence, geography, review, and shortage signals.
- Produce planning-readiness outputs after uncertainty penalties.
- Bridge Track 4 data readiness into Track 2 medical desert planning.

**Outputs**

- Risk matrix.
- Planning readiness score.
- Data readiness score.
- Regional coverage confidence.
- Planner-facing recommendations.

**Review triggers**

- Regional recommendations that depend on unresolved review items.
- Care-gap signals driven by sparse or low-trust data.
- Planning conclusions whose confidence changes after dedupe or claim review.

---

# Row Scorer v2

## Purpose

`row_scorer_v2` is the facility trust backbone that supports the agent workflow.

It gives every facility row:

- Facility trust score.
- Trust tier.
- Review-required flag.
- Reason codes.
- Component scores.

## Scoring Philosophy

v1 asked:

```text
Is the field present?
```

v2 asks:

```text
Is the field coherent, plausible, evidenced, and safe to use in planning?
```

This matters because the dataset can be highly populated while still containing scraper sentinels, bloated merged records, repeated specialty arrays, weak claims, or misleading provenance.

## Components

### Integrity

Checks:

- Valid UUID.
- Facility name present.
- Name does not look like JSON/list scraper payload.
- No column-shift sentinel such as `address_city = kie`.

### Location Coherence

Checks:

- State/city present and not sentinel values.
- PIN is valid six-digit format.
- Latitude/longitude present.
- Coordinates fall within India bounds.
- Latitude and longitude do not appear swapped or identical.

### Provenance Trust

Checks:

- Meaningful source is present.
- Source is not only a sentinel value such as `kie`.
- Source URLs or official website are available.
- Source lineage is not suspiciously bloated.

### Bloat / Contamination

Checks:

- Specialty list is not suspiciously large.
- Source URL list is not suspiciously large.
- Phone list is not suspiciously large.
- Capability, procedure, and equipment arrays are plausible.
- Row does not look like multiple scraped facilities merged together.

### Capability Evidence

Checks:

- Structured capability or specialty exists.
- Description exists.
- Planning-critical claims have supporting procedure or equipment evidence.
- Claims are not supported only by generic text.

### Deduplication

Checks:

- Row is not in a large duplicate cluster.
- Duplicate confidence is safe enough for automatic handling or review.

### Metadata Validity

Checks:

- Year established is plausible.
- Doctor count and capacity parse as numbers.
- Doctor count and capacity are not implausibly large.

## Hard Caps

Some signals cap the maximum score even when many fields are populated.

Examples:

- Missing name.
- Name looks like scraper payload.
- Column-shift sentinel.
- Coordinates outside India.
- Possible merged mega-record.
- Sentinel provenance plus bloat.

This prevents a row from scoring as planning-ready just because it contains lots of scraped text.

## Trust Tiers

```text
A: planning-ready
B: usable with caveats
C: review before planning
D: unsafe for planning
```

## Current v2 Distribution

On the local 10,088-row facility dataset:

```text
Average facility trust score: 76

A: 3,275
B: 4,010
C: 2,715
D: 88

Review-required rows: 4,196
```

Top reason codes:

```text
source_sentinel_kie: 9,970
repeated_specialty_scrape: 7,152
sentinel_plus_bloat: 6,023
specialty_bloat: 5,580
source_lineage_bloat: 5,442
source_bloat: 4,292
possible_merged_mega_record: 4,089
claim_bloat: 3,353
```

## Geographic Trust Heatmap

The app can plot facility latitude/longitude over India bounds and color each point by trust tier.

Purpose:

- Show where records are planning-ready.
- Show where rows are uncertain or unsafe.
- Make geography and data quality visible together.
- Plot up to 10,000 valid India lat/lon rows in the demo app; rows without valid in-bounds coordinates are not plotted.
- Provide zoom controls so dense clusters can be inspected without hiding the national trust picture.

Caveat:

The heatmap shows facility record trust by available coordinates. It does not prove real-world care access by itself.

---

# Demo Language

## Short Version

> The dataset is highly populated but not highly trusted. Our agents detect scraper sentinels, merged-record bloat, weak clinical claims, duplicate clusters, and geography uncertainty, then turn those signals into facility trust scores and review queues.

## Track 4 to Track 2

> We solve Track 4 by making messy healthcare facility records planning-ready. Track 2 medical desert planning becomes credible only after facility trust, claim confidence, and geolocation confidence are scored and reviewed.

## Human-in-the-Loop

> Agents handle deterministic fixes and high-confidence findings. Humans decide ambiguous merges, weak claims, conflicting specialties, ambiguous geocodes, and records whose confidence materially affects planning outputs.

## Why This Matters

> A row full of data can still be unsafe. We score trust, not just completeness.

---

# In-Product Labels

Recommended labels:

- **Facility Trust Score**
- **Trust Tier**
- **Reason Codes**
- **Geographic Trust Heatmap**
- **Planning-Ready Coverage Flag**
- **Review Before Planning**

Avoid relying only on:

- Row readiness
- Completeness score
- Field presence

Those are useful signals, but they do not capture the core data-quality risk.
