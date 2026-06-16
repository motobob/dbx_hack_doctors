# Score Guide

Use this when explaining the percentage scores in the demo.

## Short Version

The percentages are **planning readiness signals**, not clinical truth.

High score means fewer known blockers. Low score means the app should create cleanup actions before a planner trusts the data.

## Data Consistency

**Meaning:** the overall readiness score for the current resulting state.

**Formula:**

- 25% Completeness
- 20% Dedupe health
- 20% Contradictions
- 15% Location quality
- 10% Evidence quality
- 10% Provenance

**Demo line:** "This is our roll-up of whether the data is safe enough to use for planning. It is weighted toward the problems that most distort care-gap decisions."

## Completeness

**Meaning:** percent of records with minimum planning fields populated: facility name, at least city or state, and description.

**Demo line:** "Can we understand what this row is and where it roughly belongs?"

## Dedupe Health

**Meaning:** percent of rows not sitting inside duplicate clusters.

**Demo line:** "If this is low, we may be over-counting facilities and making a region look better served than it is."

## Contradictions

**Meaning:** estimated share of records without suspicious capability conflicts.

**Demo line:** "If this is low, the app thinks some claimed services may conflict with other evidence and need review."

## Location Quality

**Meaning:** percent of records with city, state, and PIN populated.

**Demo line:** "If this is low, geography planning may confuse missing location data with a true medical desert."

## Evidence Quality

**Meaning:** percent of records with both descriptive text and capability or specialty evidence.

**Demo line:** "If this is low, clinical claims like ICU, NICU, or emergency care are not well supported."

## Provenance

**Meaning:** percent of records with a source value.

**Demo line:** "Can a reviewer trace where this record came from?"

## Import Readiness

**Meaning:** percent of uploaded rows that have enough required fields to enter the pipeline without manual mapping.

**Demo line:** "This tells us whether the import can flow into agents or needs column/field review first."

## Agent Readiness Scores

**QA quality:** average completeness score across identity, location, capability, provenance, and metadata groups.

**Data readiness:** risk-agent roll-up of whether the dataset is clean enough to trust after checks.

**Planning readiness:** risk-agent estimate of whether the resulting state is safe enough for allocation or medical desert planning.
