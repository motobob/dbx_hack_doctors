# Action Workflow Design

This document defines how recommendations become actionable work packets in Data Readiness Desk.

The product goal is not to show generic AI advice. The product goal is to turn data-readiness findings into small, auditable workflows that a data steward, clinical reviewer, planner, or safe AI agent can complete.

## Design Principle

Every action must answer four questions:

1. What exact rows, claims, or rules are involved?
2. What evidence supports the recommendation?
3. What state change will happen if the user or agent applies it?
4. What audit record proves why that change was made?

If an action cannot answer those questions, it is still a finding, not an action.

## Action Packet Contract

The backend emits action rows from `app/lib/reparser.py`. The core columns are still useful for tables and filters:

- `action_id`
- `priority`
- `issue_type`
- `recommendation`
- `owner`
- `confidence`
- `status`
- `lift_points`
- `evidence`

Richer behavior lives in the JSON payload persisted through `evidence_json`:

- `action_kind`: frontend renderer selector, such as `duplicate_merge` or `auto_applied`.
- `workflow`: the operational workflow name, such as `merge_resolver`.
- `records`: row-level snapshots needed to make the decision.
- `field_choices`: selectable canonical field options for merge workflows.
- `proposed_result`: the state or metadata that will exist after approval/application.
- `evidence_items`: structured evidence cards with `label`, `value`, and optional `tone`.
- `safe_rules`: deterministic rules an agent can apply without human approval.
- `claim_tests`: evidence gates for clinical/capability claims.
- `audit_effect`: plain-language description of the audit event created by the decision.
- `decision_required`: whether a human decision is needed.

Unity Catalog mode stores these fields in `result.action_recommendations.evidence_json`. Local mode stores them in `app/state/last_run.json`.

## Workflows

### Duplicate Merge

`action_kind: duplicate_merge`

Duplicate merge actions use a merge resolver, not a plain approve button.

The UI shows:

- candidate facility rows side by side
- high-signal comparison fields
- selectable canonical field values
- proposed canonical facility output
- merge audit effect

Approve means:

- persist the chosen canonical field values in the decision note and audit event
- mark the action `Approved`
- treat the duplicate cluster as resolved for the current result state

Reject means:

- mark the action `Rejected`
- record that this pair or cluster should not be suggested as a duplicate again without new evidence

Needs review means:

- keep the item open
- preserve reviewer note and routing context

### Location Cleanup

`action_kind: location_cleanup`

Location cleanup can be agent-ready when the proposed fixes are deterministic and bounded.

Safe examples:

- trim blank-like values
- normalize PIN formatting
- infer state only when a PIN maps to exactly one state

Unsafe examples:

- infer a state from a multi-state PIN
- guess city from a partial address
- overwrite source geography with a model guess

Apply safe fix means:

- mark deterministic repairs as `Applied`
- send ambiguous records back to review
- write rule IDs and affected-row counts to audit

### Capability Evidence Review

`action_kind: capability_review`

Capability review protects planning metrics from weak clinical claims.

The UI shows:

- row snapshots containing the claim
- evidence tests required for approval
- planning impact

Confirm claim means:

- the claim can count toward trusted capability coverage
- the decision note should cite the evidence source

Reject claim means:

- the raw claim remains visible
- trusted capability coverage excludes the claim

Needs more evidence means:

- the claim remains open and should not affect trusted planning counts

### Tag Triage

`action_kind: tag_triage`

Scratchpad tags are lightweight routing instructions. They should become review slices, not vague notes.

Apply tags means:

- preserve the tags as routing metadata
- use them in the next parse to build steward queues

Skip tags means:

- keep the scratchpad content but do not use tags for queue routing

### Auto-Applied Agent Actions

`action_kind: auto_applied`

Some AI agent actions are auto-applied because they only add derived metadata and do not overwrite trusted source fields.

Current auto-applied actions:

- source provenance fingerprints
- capability evidence scores
- review queue routing

Auto-apply is allowed only when all of the following are true:

- the action is deterministic or rule bounded
- the action is additive
- the source row values remain unchanged
- the action writes enough metadata to explain itself later
- a human can reopen or inspect the action

Auto-apply is not allowed when:

- the action changes identity fields
- the action changes clinical capability truth
- the action resolves duplicate records
- the action infers ambiguous geography
- the action would affect planning counts without a reviewer gate

## Status Semantics

- `Ready`: agent can apply a safe fix, but it has not been applied yet.
- `Open`: action exists and needs routing or review.
- `Needs review`: human review is explicitly required.
- `Needs evidence`: reviewer found the action plausible but under-supported.
- `Approved`: human approved the proposed state change.
- `Applied`: safe agent action has been applied.
- `Rejected`: human rejected the proposed state change.

Closed statuses are `Approved`, `Applied`, and `Rejected`.

## Frontend Rendering

The Actions tab dispatches on `action_kind`:

- `duplicate_merge` -> merge resolver
- `location_cleanup` -> geo cleanup safe-fix panel
- `capability_review` -> evidence gate
- `tag_triage` -> review slice builder
- `auto_applied` -> applied agent audit panel
- unknown kinds -> generic evidence/proposed-result panel

The queue table remains intentionally compact. The selected action panel is where the work happens.

## Decision Notes

Decision notes are not optional decoration. They are the human-readable part of the audit record.

For merge approvals, the UI can prefill canonical field choices into the note.

For evidence approvals or rejections, the note should identify:

- proof source
- reviewer rationale
- any source preference
- uncertainty that should survive into planning

For auto-applied actions, notes are not required because the action is already closed, but reopening should require a note.

## Adding A New Action Type

To add a new action type:

1. Add an action payload helper in `app/lib/reparser.py`.
2. Set `action_kind`, `workflow`, `evidence_items`, `proposed_result`, and `audit_effect`.
3. Include rows or rules that make the action executable.
4. Add a renderer in `app/frontend/src/main.jsx`.
5. Add CSS only for genuinely new layout needs.
6. Decide whether the action can ever be `auto_applied`.
7. Document approval, rejection, and audit effects in this file.

Do not add a new action type that only changes button labels. The action must expose the actual work surface.
