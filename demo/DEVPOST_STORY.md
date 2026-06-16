# Timesharerer Doctors

## Devpost General Info

**Project name:** Timesharerer Doctors

**Elevator pitch:** Trust-first data readiness for healthcare planners: agents clean messy facility records, humans approve risky calls, and trusted data powers medical desert recommendations.

**Shorter pitch option:** Agents turn messy healthcare facility data into trusted cleanup actions and medical desert recommendations.

**Tagline option:** Clean healthcare data first. Plan medical desert outreach second.

**Slogan:** Inspire people to go further and share more.

**Built with:** Databricks Apps, Unity Catalog, Databricks SQL, Databricks Jobs, Python, FastAPI, React, Vite, pandas.

**Tracks:** Track 4: Data Readiness Desk; downstream Track 2: Medical Desert Planner.

**One-liner for judges:** Timesharerer Doctors turns 10,000 messy facility records into a trust-scored map, a proof/reject action queue, and risk recommendations that link back to the cleanup work behind them.

## Inspiration

Healthcare planners cannot make good decisions from data they do not trust. The dataset gave us more than 10,000 healthcare facility records across India, but the records were not planning-ready: duplicate facilities, sparse locations, ambiguous PIN codes, uneven free-text clinical claims, and specialties that sometimes disagree with descriptions.

Our inspiration was the idea that medical desert planning should come after data readiness. Before asking where care is missing, Timesharerer Doctors asks which facility records are trustworthy enough to count.

The project slogan is: "Inspire people to go further and share more." For this demo, that means helping healthcare teams share trustworthy facility data and go further with planning decisions that are backed by evidence.

## What it does

Timesharerer Doctors is a Databricks App that turns messy healthcare facility data into a trusted planning workflow.

Users can inspect the current dataset through a Geographic Score Heatmap, click facility dots to reveal row notes and linked work, drag in an XLS/XLSX/CSV import, run an agent-led readiness pipeline, and review the resulting proof/reject queue. The app surfaces row uncertainty tiers, duplicate clusters, sparse locations, weak capability claims, evidence issues, and planning-critical recommendations that need human confirmation.

The final output is not just a cleanup report. It is an actionable risk-planning view that starts from trusted geography: where care gaps may be real, where evidence is weak, where bad data could be creating false confidence, and which cleanup actions must be resolved before planners trust the recommendation.

## How we built it

We built Timesharerer Doctors as a Databricks App with a React/Vite frontend and FastAPI backend. The app is designed for Unity Catalog source/result/audit state, with a local/offline mode for repeatable development and demos.

The workflow separates immutable source data, working agent outputs, and trusted resulting state. A ten-stage pipeline handles ingestion, QA, PIN-code context, NFHS survey context, dedupe, evidence checks, geography, shortage signals, human review, and risk synthesis.

The core scoring shift is `row_scorer_v2`: the app does not ask only whether a field is populated. It asks whether a facility row is coherent, evidenced, geospatially plausible, non-duplicative, and safe to count in planning.

We also built a demo import workbook with intentional duplicates, sparse fields, weak claims, and suspicious metadata so the full loop can be shown in three minutes.

## Challenges we ran into

The hardest product challenge was keeping the app honest. It would be easy to show clean-looking scores, but healthcare planning needs evidence and uncertainty. We designed the app so uncertain records become review work instead of disappearing behind a dashboard number.

The hardest platform challenge was making the app resilient across local development and Databricks Apps. We handled Unity Catalog access, SQL warehouse behavior, app startup latency, cloud-fetch issues, and cases where Databricks compute or job runs were unavailable. That led us to add explicit diagnostics and a `./run.sh dev local` mode for offline demos.

## Accomplishments that we're proud of

We are proud that the app tells a complete Track 4 to Track 2 story: agents triage messy data, humans proof the planning-critical calls, and the trusted resulting state powers medical desert recommendations with facts, next steps, and links back to cleanup work.

We are also proud of the human-in-the-loop design. Timesharerer Doctors does not pretend weak evidence is fact: the heatmap and row uncertainty distribution make weak rows visible before they influence planning. Every important recommendation carries owner, confidence, evidence, next step, status, and reviewer notes.

## What we learned

We learned that data readiness is not just data cleaning. It is trust management. A row can look complete but be duplicated. A PIN code can exist but be ambiguous. A clinical claim can sound important but lack enough support to plan around it.

We also learned that useful agent workflows need explicit contracts: when to auto-fix, when to route to human review, when geography is too ambiguous, and when a planning recommendation should be treated as low confidence.

## What's next for Timesharerer Doctors

Next, we want to persist every agent output, recommendation, decision, and audit event into Unity Catalog work/result/audit tables. We also want deeper duplicate clustering, richer evidence extraction from descriptions, stronger geocoding repair, and reusable dataset packs for other healthcare datasets.

Long term, Timesharerer Doctors can become a planning cockpit for NGOs and public-health teams: import messy facility data, let agents find the problems, let humans confirm the material calls, and continuously produce trustworthy care-gap recommendations.
