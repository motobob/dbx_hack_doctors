# Project Plan: Databricks Hackathon — Data Readiness Desk with Planning-Ready Outputs

## Reasoning

### 1. Best track fit: start with Track 4, but design for Track 2 downstream

Your team's stated approach is fundamentally a data readiness and trust layer: clean messy facility records, triage uncertainty, and produce geolocated specialty coverage with confidence.

That maps most directly to Track 4: Data Readiness Desk because the app needs to surface data issues, contradictions, sparse fields, and review queues.

At the same time, your output should explicitly enable medical desert and risk gap planning later, which aligns with Track 2.

So the right hackathon posture is:

- Primary submission story: "We make the dataset planning-ready."
- Downstream value story: "Those cleaned, trust-weighted records can drive medical desert gap planning."

### 2. The dataset is noisy in predictable ways, so the pipeline should be structured around those failure modes

The provided data has several known quality issues:

- Nulls and sparsity in important fields:
  - `numberDoctors`, `capacity`, and `yearEstablished` are often missing.
  - `postcode` is present for nearly all but not all records.
- Duplicates and near-duplicates:
  - Facilities may appear multiple times with slight name or address variations.
- Mismatches between structured fields and free text:
  - For example, specialties say one thing, while description or equipment fields say another.
- Claims that are unevidenced or weakly supported:
  - ICU, maternity, emergency, oncology, trauma, NICU, dialysis, and similar claims need evidence.
- Noisy, repetitive, uneven free-text evidence:
  - Description, capability, procedure, and equipment fields are claims, not truth.
- Geospatial imprecision:
  - Latitude/longitude may be off, and postcode may be missing or inconsistent.
- Ambiguous specialty mapping:
  - Controlled specialties and inferred specialties from text may disagree.
- Stale or suspicious metadata:
  - `yearEstablished` may be missing, impossible, or inconsistent with other signals.
- Source URL quality variation:
  - Some URLs will corroborate records, while others may be broken, generic, or duplicated.

These issues require a workflow that separates:

- Clear-cut automated fixes.
- Ambiguous cases for human review.
- Confidence-scored outputs for downstream planning.

### 3. Automation should handle certain cleanup, while humans handle borderline cases

The team approach from your transcript summary is the right pattern.

Agents first for:

- Primary QA.
- Standardization.
- Deduplication.
- Evidence extraction.
- Confidence scoring.

Humans second for:

- Ambiguous duplicates.
- Contradictory claims.
- Uncertain specialty mapping.
- Borderline geocodes.
- Facilities whose trust score materially changes planning outcomes.

This is important because the hackathon prompt explicitly says the app should:

- Cite underlying facility text.
- Communicate uncertainty honestly.
- Let users save or revise work.

That means the system should never pretend uncertain evidence is fact.

### 4. The app needs a trust layer, not just a cleaning layer

A non-technical planner needs answers like:

- "Can this facility really do emergency care?"
- "Which districts look like they have no maternity coverage?"
- "Which records are safe enough to count in a planning scenario?"

To support that, every record and every region should get:

- A quality status.
- A claim/evidence status.
- A confidence score.
- A review status.
- An audit trail of notes and overrides.

This creates trustworthy decision support rather than just a cleaned CSV.

### 5. Geolocated specialty coverage is the key downstream bridge to medical desert planning

Your stated output should be:

- Cleaned facility records.
- Normalized specialties and capabilities.
- Geolocation-aware coverage estimates.
- Confidence levels on those estimates.

That enables a planner to answer:

- Where real coverage exists.
- Where gaps are likely real.
- Where the problem may simply be data sparsity.

So the pipeline should distinguish:

- Care desert.
- Data desert.
- Uncertain desert.

### 6. Databricks should be the center of gravity for speed and reproducibility

To move quickly in one day:

- Use Databricks notebooks for profiling and QA.
- Use Delta tables for intermediate outputs.
- Use a simple Databricks App for the review interface.
- Keep deliverables in the Git repo for easy submission and versioning.

This keeps exploration, transformation, and app building in one place and reduces integration risk.

### 7. Minimum viable product should prioritize one tight workflow

Because of time, the MVP should focus on:

- EDA and quality assessment.
- Agent-driven cleanup and triage.
- Review queue with notes and overrides.
- Trust-weighted coverage output.
- Region-level planning view.

Anything beyond that should be treated as stretch.
