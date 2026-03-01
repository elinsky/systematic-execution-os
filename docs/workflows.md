# BAM Systematic Execution OS — Workflows & Operating Cadences

**Version:** 1.0
**Date:** 2026-03-01
**Scope:** v1 Operating System (Asana + lightweight sidecar)

---

## Table of Contents

1. [Workflow Lifecycle Specifications](#1-workflow-lifecycle-specifications)
   - 1.1 New PM Onboarding Workflow
   - 1.2 PM Need Intake and Routing Workflow
   - 1.3 Cross-Functional Delivery Workflow
   - 1.4 Weekly Operating Review Workflow
   - 1.5 Escalation / Accountability Workflow
   - 1.6 Post-Go-Live Stabilization Workflow
   - 1.7 Platform Capability Roadmap Workflow
2. [Meeting / Cadence Templates](#2-meeting--cadence-templates)
   - 2.1 Project-Specific Working Session
   - 2.2 PM Onboarding Meeting
   - 2.3 Daily Standup
   - 2.4 Weekly Operating Review
   - 2.5 PM Touchpoint / Relationship Check-In
   - 2.6 Business–Technology Coordination Meeting
   - 2.7 Monthly Roadmap / Vision Review
   - 2.8 Milestone Readiness Review
   - 2.9 Risk / Blocker Escalation Review
   - 2.10 Post-Go-Live Stabilization Review
3. [Artifact Lifecycle Rules](#3-artifact-lifecycle-rules)
4. [Dashboard / Reporting Requirements](#4-dashboard--reporting-requirements)
5. [Bot Use Case Specifications](#5-bot-use-case-specifications)

---

## 1. Workflow Lifecycle Specifications

### Design Notes

All workflows operate on the v1 domain model:
- **PMCoverageRecord** — one per PM/team
- **PMNeed** — one per discrete ask/requirement
- **Project** — one per bounded execution effort
- **Milestone** — named checkpoints with gating criteria
- **Deliverable** — concrete owned action items
- **RiskBlocker** — threats to dates, outcomes, or confidence
- **Decision** — durable record of meaningful tradeoffs
- **StatusUpdate** — structured snapshots for stakeholders

Capability, Initiative, and Dependency are v2 additions unless needed to unblock a v1 workflow.

---

### 1.1 New PM Onboarding Workflow

**Purpose:** Get an incoming PM from pipeline/pre-start to live, ensuring all promised capabilities are delivered and the PM is set up for success.

**This is the flagship workflow — every feature of the system should support it.**

#### Trigger Conditions

- New PM confirmed/contracted and assigned to an onboarding lead
- Executive or business leadership initiates onboarding
- Bot command: `"Create a new PM onboarding project for [PM name]"`

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Create PM Coverage Record** | PM name, team/pod, strategy type, region, coverage owner, go-live target date | PMCoverageRecord (stage: `pipeline` or `pre_start`) | PMCoverageRecord (created) |
| 2 | **Create Onboarding Project from template** | PM Coverage Record, onboarding lead, target go-live date | Asana project instantiated from onboarding template | Project (created), linked to PMCoverageRecord |
| 3 | **Seed default milestones** | Project ID, target go-live date | 10 default milestones created with target dates back-calculated from go-live | Milestone x10 (created, status: `not_started`) |
| 4 | **Kickoff — capture PM needs** | PM requirements discovery session, coverage owner notes | PM Needs log (5–15 items typical) | PMNeed x N (created, status: `new`) |
| 5 | **Triage and map each PM Need** | PMNeed list, Capability registry (if available) | Each need mapped to capability or new project | PMNeed (status: `triaged` → `mapped_to_existing_capability` or `needs_new_project`) |
| 6 | **Create deliverables and assign owners** | Mapped needs, milestone targets, stakeholder map | Deliverables created, owners assigned, due dates set | Deliverable x N (created) |
| 7 | **Track dependencies and risks** | Deliverable list, external dependencies, known risks | RiskBlockers opened for known threats | RiskBlocker x N (created), Dependency links established |
| 8 | **Run weekly onboarding meetings** | PMCoverageRecord, Project, Milestones, Deliverables, Blockers | Updated stages, commitments, escalations, new needs | PMCoverageRecord (stage updated), Milestone (confidence updated), RiskBlocker (updated/resolved) |
| 9 | **Milestone: Go-Live Ready** | All milestones met, acceptance criteria validated | PMCoverageRecord stage → `go_live_ready` | PMCoverageRecord, Milestone (status: `complete`) |
| 10 | **Mark PM Live** | Go-live confirmed by PM and business lead | PMCoverageRecord stage → `live`, StatusUpdate published | PMCoverageRecord, StatusUpdate (created) |
| 11 | **Run post-go-live stabilization** | Stabilization checklist, early issues, PM feedback | Follow-on PM Needs, support actions, closure decision | PMNeed (new), RiskBlocker (resolved), Deliverable (support items) |
| 12 | **Transition to steady-state** | Stabilization criteria met | PMCoverageRecord stage → `steady_state`, project archived | PMCoverageRecord (stage: `steady_state`), Project (archived) |

#### Default Onboarding Milestones (with sequence)

1. **Kickoff** — onboarding formally started, PM briefed on process
2. **Requirements Confirmed** — all PM needs captured and triaged
3. **Market Data Ready** — real-time market data feeds confirmed operational
4. **Historical Data Ready** — historical data coverage confirmed per PM specs
5. **Alt Data Ready** — alternative data sources confirmed (if applicable)
6. **Execution Ready** — DMA, broker connectivity, execution monitoring confirmed
7. **UAT Complete** — PM has signed off on user acceptance testing
8. **Go-Live Ready** — all gates passed, final check complete
9. **PM Live** — PM trading live on the platform
10. **Stabilization Complete** — 2–6 weeks post-live, all early issues resolved

#### State Transitions for PMCoverageRecord.onboarding_stage

```
pipeline → pre_start → requirements_discovery → onboarding_in_progress
  → uat → go_live_ready → live → stabilization → steady_state
```

Backwards transitions allowed for: `uat → onboarding_in_progress` (failed UAT), `go_live_ready → onboarding_in_progress` (gate failure).

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| PM needs cannot be mapped to any existing capability | Open `needs_new_project` PM Need, escalate to roadmap review |
| Milestone missed by > 1 week | Auto-open RiskBlocker, flag in next operating review |
| Owner unassigned on deliverable > 3 business days | Alert coverage owner, surface in operating review |
| UAT fails | Revert PMCoverageRecord to `onboarding_in_progress`, open issues as PM Needs, set new UAT target |
| PM Coverage Record missing required fields at kickoff | Block project creation until filled — template enforcement |

#### Completion Criteria

- PMCoverageRecord.stage = `steady_state`
- All 10 default milestones status = `complete`
- All PM Needs status = `delivered`, `mapped_to_existing_capability`, or `deferred` with PM acceptance
- No open RiskBlockers of severity `high` or `critical`
- StatusUpdate published with closure summary

---

### 1.2 PM Need Intake and Routing Workflow

**Purpose:** Convert every PM ask — however vague — into a mapped, prioritized, owned, visible work item.

**Rule:** No PM ask should remain as unstructured free text for more than one business day.

#### Trigger Conditions

- PM verbal or written request captured by coverage owner
- Asana form submission from PM (recommended intake path)
- Discovery during onboarding requirements session
- Escalation reveals an underlying unmet need
- Bot command: `"Log a new PM need for [PM]."`

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Capture PM Need** | PM name, need title, problem statement, business rationale, requested_by, category, urgency | PMNeed (status: `new`) | PMNeed (created) |
| 2 | **Validate completeness** | Required fields: title, PM, category, urgency, business_rationale | Validation pass/fail; missing fields flagged | PMNeed (rejected back to submitter if incomplete) |
| 3 | **Triage** | PMNeed, coverage owner judgment | Category confirmed, urgency/impact scored, desired_by_date set | PMNeed (status: `triaged`) |
| 4 | **Check for existing solution** | Capability registry, active projects list | Match found or not | No object change if match found; link established |
| 5a | **If existing capability applies** | Capability ID, current maturity, timeline | PMNeed linked to capability, expectation set with PM | PMNeed (status: `mapped_to_existing_capability`), linked_capability_id set |
| 5b | **If new project / backlog needed** | Prioritization judgment, business impact, urgency | New project created or added to backlog | PMNeed (status: `needs_new_project`), Project (created or PMNeed queued to backlog) |
| 6 | **Define success criteria** | PMNeed, coverage owner, PM input | Acceptance criteria documented on need and linked project/milestone | PMNeed.resolution_path filled, Milestone.acceptance_criteria set |
| 7 | **Assign owners** | Project owner, tech partner, delivery team | Owner fields populated | Deliverable.owner, Project.owner set |
| 8 | **Include in next operating review** | PMNeed, linked project | Surfaced in operating review agenda | StatusUpdate (next operating review agenda) |

#### Mandatory Fields for PM Need Intake (v1)

- `title` — short, specific description
- `pm_id` — which PM/team this is for
- `category` — one of the defined categories
- `urgency` — `critical`, `high`, `medium`, `low`
- `business_rationale` — one paragraph minimum
- `requested_by` — person who raised this
- `date_raised` — auto-populated

**Optional but strongly recommended:**
- `desired_by_date`
- `business_impact` — quantified or qualified impact statement
- `problem_statement` — detailed description

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| Duplicate need detected (same PM, similar category) | Flag for deduplication; link to existing need or close as duplicate |
| Need cannot be categorized | Default to `other`, flag for triage |
| No owner available for 5+ business days | Escalate to operating review, PM should be notified |
| Need sits in `triaged` for > 5 business days with no routing decision | Alert coverage owner |

#### Completion Criteria

- PMNeed.status in (`delivered`, `mapped_to_existing_capability`, `deferred`, `cancelled`)
- If `delivered`: linked project/capability completed
- If `deferred`: PM informed and accepted deferral with expected timeframe
- If `cancelled`: rationale documented

---

### 1.3 Cross-Functional Delivery Workflow

**Purpose:** Translate a business-defined need into delivered, validated work across business, technology, and partner teams.

**Rule:** Every tech effort should tie back to a clear business outcome traceable to a PM Need or Capability Gap.

#### Trigger Conditions

- PMNeed routed to `needs_new_project`
- Capability gap identified in roadmap review
- Escalation requiring structural resolution
- Business leadership request for new initiative

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Define project from need or gap** | PMNeed or capability gap, business objective | Project created with name, type, objective, success criteria, target date | Project (created) |
| 2 | **Confirm ownership** | Project, business lead, tech lead | Project.owner, Project.primary_pm_ids set | Project (updated) |
| 3 | **Break into milestones** | Project objective, target date, phase logic | 3–7 milestones created with target dates and gating conditions | Milestone x N (created) |
| 4 | **Break into deliverables** | Milestones, work breakdown | Deliverables created per milestone with owners and due dates | Deliverable x N (created) |
| 5 | **Cross-functional assignment** | Deliverables, stakeholder map, tech partner alignment | Each deliverable assigned to a single named owner | Deliverable.owner set for all items |
| 6 | **Identify and record dependencies** | Deliverable list, external dependencies | Dependencies documented | Dependency records created (or noted in Asana task dependencies) |
| 7 | **Baseline risks** | Deliverables, dependencies, known constraints | Initial RiskBlockers opened for identified threats | RiskBlocker x N (created) |
| 8 | **Weekly progress review** | Project, milestones, deliverables, blockers | Updated dates, owners, milestone confidence, new blockers | All objects updated weekly |
| 9 | **Escalate blockers** | RiskBlockers, milestone impact | Escalations triggered, decisions recorded | RiskBlocker (escalation_status updated), Decision (created if tradeoff needed) |
| 10 | **Business-side acceptance** | Milestone acceptance criteria, PM confirmation | Final milestone marked complete | Milestone (status: `complete`), PMNeed (status: `delivered`) |
| 11 | **Project closure** | All milestones complete, no open high-severity blockers | StatusUpdate published, project archived | Project (archived), StatusUpdate (created) |

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| Tech team cannot commit to a date | Open RiskBlocker, escalate to Business-Technology Coordination meeting |
| Scope creep adding new deliverables | New PMNeed created for expansion work, separate from original project unless formally accepted |
| Owner leaves or unavailable | Project flagged as at-risk, coverage owner reassigns within 2 business days |
| Tech delivers feature that does not meet acceptance criteria | Deliverable rejected, re-opened, linked to new milestone date |

#### Completion Criteria

- All milestones status = `complete`
- All milestones have passed acceptance criteria validation
- Business-side sign-off captured (PM and/or coverage owner)
- Originating PMNeed(s) status = `delivered`
- StatusUpdate published

---

### 1.4 Weekly Operating Review Workflow

**Purpose:** Run the execution system across all active work. Identify what is slipping, at risk, or needs decisions, and leave with a clear action list.

**Rule:** The system generates the agenda — prep time should be under 15 minutes.

#### Trigger Conditions

- Weekly cadence (recommended: Monday morning or Friday EOW)
- Automated reminder from sidecar scheduler
- Bot command: `"Prepare tomorrow's weekly operating review."`

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Auto-generate agenda** | All active projects, all open deliverables, all milestones in 14-day window, all open RiskBlockers, all pending Decisions | Structured agenda with sections: overdue, at risk, decisions, achievements | StatusUpdate (draft agenda) |
| 2 | **Overdue deliverables triage** | Deliverables past due_date with status not `complete` | Re-prioritized or escalated deliverables, new due dates | Deliverable (due_date updated, owner confirmed) |
| 3 | **Milestone slip review** | Milestones with target_date < today and status != `complete` | Slip impact assessed, replanned dates set, RiskBlockers opened if needed | Milestone (target_date updated), RiskBlocker (opened) |
| 4 | **PMs at risk review** | PMCoverageRecord with health_status = `yellow` or `red`, PMs with aging blockers | Escalation decisions, priority adjustments | PMCoverageRecord (health updated), RiskBlocker (escalation_status updated) |
| 5 | **Decisions needed** | Decision records with status = `pending` | Decisions assigned to approvers, deadlines set | Decision (approver assigned, deadline set) |
| 6 | **Reprioritization** | Deliverable and project list, business priority inputs | Updated priority fields | Project (priority updated), Deliverable (priority updated) |
| 7 | **Summary for leadership** | Meeting outputs | Leadership talking points drafted | StatusUpdate (initiative-level) |
| 8 | **Publish status updates** | Updated records | StatusUpdates published for all active projects | StatusUpdate x N (published) |

#### Agenda Template (Auto-Generated)

```
WEEKLY OPERATING REVIEW — [DATE]
Generated: [timestamp]

1. CRITICAL ITEMS (requires decision today)
   [auto: Decisions pending > 5 days or blocking milestone]

2. AT-RISK PMs (health = red or yellow)
   [auto: PMCoverageRecords with health != green]

3. OVERDUE DELIVERABLES (past due date, not complete)
   [auto: Deliverables where due_date < today and status != complete]

4. MILESTONE SLIPS (target date slipped since last review)
   [auto: Milestones where target_date changed in last 7 days OR target_date < today]

5. OPEN BLOCKERS BY SEVERITY
   [auto: RiskBlockers grouped by severity, ordered by age_days desc]

6. UPCOMING MILESTONES (next 14 days)
   [auto: Milestones where target_date BETWEEN today AND today+14]

7. WINS / COMPLETIONS THIS WEEK
   [auto: Deliverables and milestones completed in last 7 days]

8. DECISIONS NEEDED
   [auto: Decision records with status = pending, ordered by urgency]
```

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| No project updates in past 7 days | Flag as "stale" in agenda; owner pinged before meeting |
| Agenda too long (> 20 items per section) | Auto-prioritize to top 5 per section by severity + age |
| Meeting participant unavailable for decision | Decision deferred with explicit new date, not left open-ended |

#### Completion Criteria

- All agenda items reviewed or explicitly deferred to next cycle
- All overdue deliverables have updated due dates or escalation path
- At-risk PMs have an action or escalation assigned
- StatusUpdates published for all active projects
- Leadership talking points drafted

---

### 1.5 Escalation / Accountability Workflow

**Purpose:** Surface delays and ambiguity quickly; assign ownership to resolution; prevent the "moving bullseye" problem where tech timelines slip without business visibility.

#### Trigger Conditions (automatic)

- Milestone target date slipped by > 5 business days
- Deliverable overdue by > 3 business days
- PMCoverageRecord.health_status changes to `yellow` or `red`
- Decision pending > 7 business days
- Deliverable.owner is null/unset > 3 business days
- Same PM has 3+ open blockers simultaneously
- RiskBlocker.age_days exceeds severity threshold (see table below)

**Age thresholds by severity:**

| Severity | Alert threshold |
|----------|-----------------|
| Critical | 1 business day |
| High | 3 business days |
| Medium | 7 business days |
| Low | 14 business days |

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Open or update RiskBlocker** | Trigger condition, impacted PM/project/milestone | RiskBlocker (created or updated) | RiskBlocker (created/updated) |
| 2 | **Link impacted artifacts** | RiskBlocker, impacted_pm_ids, impacted_project_ids, impacted_milestone_ids | Impact scope documented | RiskBlocker (relationships set) |
| 3 | **Assign escalation owner** | RiskBlocker, available stakeholders | RiskBlocker.owner set within 1 business day | RiskBlocker (owner assigned) |
| 4 | **Record decision needed (if applicable)** | Context, options, required approver | Decision record created | Decision (created, status: `pending`) |
| 5 | **Surface in operating review** | RiskBlocker, Decision | Agenda item in next operating review | StatusUpdate (agenda updated) |
| 6 | **Resolve / replan / re-scope** | Escalation owner decision, tech inputs | RiskBlocker resolved or replanned; Milestone dates updated | RiskBlocker (status: `resolved`), Milestone (target_date updated) |
| 7 | **Close escalation** | Resolution confirmed | RiskBlocker closed, Decision finalized, StatusUpdate published | RiskBlocker (status: `resolved`), Decision (status: `decided`), StatusUpdate (published) |

#### Escalation Severity Definitions

| Severity | Definition |
|----------|------------|
| `critical` | Blocking go-live for a PM; no workaround; requires leadership action within 24 hours |
| `high` | Blocking key milestone; workaround may exist but is suboptimal; action required within 3 days |
| `medium` | Threatening a milestone but not blocking it yet; action required within a week |
| `low` | Monitoring item; may become high if unresolved |

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| No escalation owner found | Default to coverage owner; flag in operating review |
| Escalation stalls in `open` > severity threshold | Auto-escalate to business lead; increase severity one level |
| Decision made without required approver | Decision flagged as `pending_ratification`; cannot close RiskBlocker until ratified |

#### Completion Criteria

- RiskBlocker.status = `resolved`
- Impacted milestones have updated dates or re-scope decisions
- Decision record closed if decision was required
- PM Coverage Record health updated to reflect resolution
- StatusUpdate published for impacted projects

---

### 1.6 Post-Go-Live Stabilization Workflow

**Purpose:** Ensure the PM is genuinely functional and supported after launch. "Live" is not the finish line.

#### Trigger Conditions

- PM Live milestone marked complete
- PMCoverageRecord.stage transitions to `live`

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Activate stabilization checklist** | PMCoverageRecord, onboarding project | Stabilization section activated in Asana project | Deliverable x N (stabilization checklist items) |
| 2 | **Capture early issues** | PM feedback, monitoring alerts, team observations | Issues logged as RiskBlockers or new PMNeeds | RiskBlocker (created), PMNeed (created) |
| 3 | **Triage issues: support vs roadmap** | Issues list | Support items assigned immediately; roadmap items queued as PMNeeds | Deliverable (support items), PMNeed (roadmap items) |
| 4 | **Weekly stabilization review** | Stabilization checklist, open issues, PM feedback | Updated issue status, unblocked items, PM sentiment | RiskBlocker (updated), Deliverable (updated), PMCoverageRecord (health updated) |
| 5 | **Check stabilization criteria** | Stabilization checklist completion, open issues | Go/no-go for closure | All stabilization Deliverables status confirmed |
| 6 | **Close stabilization** | All stabilization criteria met | PMCoverageRecord.stage → `steady_state`, project archived | PMCoverageRecord (stage: `steady_state`), Project (archived), StatusUpdate (published) |

#### Stabilization Checklist (Default)

- [ ] PM can run live trading on platform
- [ ] Data feeds confirmed accurate and stable
- [ ] Execution (DMA/broker) confirmed working
- [ ] Monitoring / alerting in place
- [ ] PM knows escalation path for issues
- [ ] No unresolved critical or high severity blockers
- [ ] Open issues logged and triaged
- [ ] Roadmap items queued as PM Needs
- [ ] PM sentiment check: PM satisfied with onboarding outcome
- [ ] Coverage owner sign-off

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| Critical issue found post-go-live | Open critical RiskBlocker, trigger Escalation workflow, may pause stabilization closure |
| PM expresses dissatisfaction | Open PMNeed to capture unmet expectations; escalate to operating review |
| Stabilization drags > 6 weeks | Force review in monthly roadmap meeting; determine if structural issue |

#### Completion Criteria

- All stabilization checklist items complete
- No open critical/high RiskBlockers
- PMCoverageRecord.stage = `steady_state`
- Follow-on PMNeeds captured and triaged
- StatusUpdate published with go-live outcome summary

---

### 1.7 Platform Capability Roadmap Workflow

**Purpose:** Convert repeated PM needs into shared platform investments, avoiding repeated bespoke solutions.

**Note:** This workflow bridges v1 (PM Need intake) and v2 (full Capability and Initiative objects). In v1, Capability records are lightweight; Initiative-level tracking is optional.

#### Trigger Conditions

- Monthly roadmap review meeting
- 3+ PM Needs in same category unresolved within a rolling 60-day window
- Manual trigger by business/tech leadership
- Quarterly capability audit

#### Step-by-Step Flow

| Step | Action | Inputs Required | Outputs Generated | Domain Objects Touched |
|------|--------|-----------------|-------------------|------------------------|
| 1 | **Aggregate PM Needs** | All PMNeeds from last 90 days with status not `delivered` or `cancelled` | Aggregated need list by category | Read-only view of PMNeed objects |
| 2 | **Cluster repeated asks** | PMNeed category distribution, business rationale similarity | Capability gap clusters identified | PMNeed (tagged with capability cluster) |
| 3 | **Assess business leverage** | Cluster analysis, dependent PMs count, business impact scores | Ranked capability gap list | Decision (created: capability prioritization) |
| 4 | **Create / update Capability record (v1: lightweight)** | Capability name, domain, owner team, known gaps, dependent PMs | Capability reference project created in Asana | v1: "Capability - [Name]" project created |
| 5 | **Create roadmap projects** | Capability priority, owner, scope | Projects created for top-priority capability gaps | Project (created, type: `capability_build`) |
| 6 | **Sequence milestones** | Project timeline, dependency logic | Foundation / v1 / expansion milestones set | Milestone x N (created) |
| 7 | **Track PM unblocking** | Capability delivery milestones, PM needs | PM Needs linked to capability milestones | PMNeed (linked_project_ids updated) |
| 8 | **Review monthly** | Capability roadmap, new PM needs, delivery progress | Roadmap adjustments, new capability gaps | Project (priority updated), PMNeed (new) |

#### Error / Exception Handling

| Exception | Handler |
|-----------|---------|
| Capability owner team disputes ownership | Open Decision record; escalate to Business-Technology Coordination meeting |
| PM need cannot wait for capability build | Short-term bespoke solution authorized via Decision; PM Need marked `in_progress` separately |
| Capability build blocked by tech capacity | Open RiskBlocker; surface in monthly roadmap review |

#### Completion Criteria (per capability project)

- Capability project milestones complete
- All linked PMNeeds status = `delivered` or `mapped_to_existing_capability`
- Capability marked `available` or `stable` in registry

---

## 2. Meeting / Cadence Templates

### Design Principle

The system should generate meeting prep automatically from artifact state. The coverage owner should spend no more than 15 minutes preparing for any recurring meeting. Every template below specifies what the system can auto-generate vs. what requires human input.

---

### 2.1 Project-Specific Working Session

**Cadence:** Weekly (or as needed)
**Duration:** 30–60 minutes
**Participants:** Project owner, key deliverable owners, coverage owner, relevant tech leads

#### Required Inputs

- Project object (status, priority, target_date, success_criteria)
- Milestones for this project (status, target_date, confidence, acceptance_criteria)
- Deliverables (status, owner, due_date, blocked_by)
- Open RiskBlockers linked to this project
- Open Decisions linked to this project

#### Auto-Generated Prep (system produces)

- List of overdue deliverables with owner and age
- Milestone confidence scores and status
- Open blockers sorted by severity
- Pending decisions with age
- Brief status narrative from last StatusUpdate

#### Human Input Required

- Progress updates on in-progress deliverables
- Revised date estimates
- New risk/blocker identification
- Decision inputs

#### Meeting Template / Checklist

```
PROJECT WORKING SESSION — [PROJECT NAME] — [DATE]

PREPARED AUTOMATICALLY:
---
1. Status snapshot (from last StatusUpdate)
   Overall health: [auto]
   Days to target: [auto]
   Last updated: [auto]

2. Overdue deliverables [auto-list]
   - [deliverable] | Owner: [name] | Was due: [date] | [age] days overdue

3. Active milestones [auto-list]
   - [milestone] | Target: [date] | Confidence: [low/med/high] | Status: [status]

4. Open blockers [auto-list]
   - [blocker] | Severity: [sev] | Age: [days] | Owner: [name]

5. Pending decisions [auto-list]
   - [decision] | Requested from: [approver] | Age: [days]

DISCUSSION AGENDA (human-driven):
---
6. Progress updates — walk the overdue and in-flight items
7. Blocker resolution — what can be unblocked today?
8. Date adjustments — any milestones that need replanning?
9. New risks / dependencies to capture
10. Decisions needed — force any pending decisions

OUTPUTS TO CAPTURE IN SYSTEM:
---
[ ] Updated deliverable due dates / owners
[ ] Milestone confidence scores updated
[ ] New blockers logged
[ ] Decisions recorded or closed
[ ] StatusUpdate published after meeting
```

#### Data Views Needed

- Project detail view (all milestones, deliverables, blockers, decisions for one project)
- Asana project board for this project

#### Automation Support

- Pre-meeting report auto-generated 2 hours before scheduled meeting (v2)
- StatusUpdate draft auto-generated post-meeting from field changes (v2)

---

### 2.2 PM Onboarding Meeting

**Cadence:** Weekly until go-live; biweekly during stabilization
**Duration:** 30–45 minutes
**Participants:** PM (or PM team lead), coverage owner, relevant tech/ops stakeholders

#### Required Inputs

- PMCoverageRecord (stage, health, go_live_target_date, top_open_needs, top_blockers)
- Onboarding Project (milestones, deliverables, status)
- All open PMNeeds for this PM
- Open RiskBlockers for this PM

#### Auto-Generated Prep (system produces)

- PM stage and days to target go-live
- Milestone completion % and next milestone with target date
- Open needs by status (new, triaged, in_progress, blocked)
- Open blockers sorted by severity and age
- Deliverables due in next 7 days

#### Human Input Required

- PM feedback on current state
- Confirmation of upcoming milestone readiness
- New asks or concerns from PM

#### Meeting Template / Checklist

```
PM ONBOARDING MEETING — [PM NAME] — [DATE]

PREPARED AUTOMATICALLY:
---
1. PM Coverage snapshot
   Stage: [auto] | Health: [auto] | Go-live target: [auto] | Days remaining: [auto]
   Last touchpoint: [auto]

2. Milestone progress [auto]
   Completed: [X/10]
   Next milestone: [name] | Target: [date] | Confidence: [auto]
   At-risk milestones: [auto-list]

3. Open PM needs [auto-list by status]
   New: [count] | Triaged: [count] | In Progress: [count] | Blocked: [count]
   Critical/high urgency: [auto-list]

4. Open blockers [auto-list]
   - [blocker] | Severity: [sev] | Age: [days] | Owner: [name]

5. Deliverables due next 7 days [auto-list]

DISCUSSION AGENDA (human-driven):
---
6. PM check-in — how is the PM feeling about progress?
7. New needs — any asks not yet captured?
8. Blocker review — what can we unblock?
9. Milestone commitments — confirm next milestone date
10. Action items for next meeting

OUTPUTS TO CAPTURE IN SYSTEM:
---
[ ] PMCoverageRecord.onboarding_stage updated if changed
[ ] PMCoverageRecord.health_status updated
[ ] PMCoverageRecord.last_touchpoint_date updated to today
[ ] New PMNeeds logged
[ ] New blockers logged
[ ] Milestone confidence scores updated
[ ] Commitments documented as Deliverables with owners and due dates
```

#### Data Views Needed

- PM Coverage Record detail view
- PM onboarding project (milestones + deliverables)
- PM Needs filtered to this PM

---

### 2.3 Daily Standup

**Cadence:** Daily (only for hot workstreams)
**Duration:** 10–15 minutes
**Participants:** Active delivery team for a specific high-urgency workstream
**Trigger:** Imminent launch, severe blocker, cutover, production incident, compressed timeline

#### Required Inputs

- Deliverables due in next 72 hours (for the relevant project)
- Active RiskBlockers for this project
- Any overnight changes (status updates, new blockers, resolved items)

#### Auto-Generated Prep (system produces)

- Deliverables due today and next 2 days, sorted by owner
- Active blockers, sorted by severity
- Any items that changed status since last standup

#### Meeting Template / Checklist

```
DAILY STANDUP — [PROJECT/WORKSTREAM] — [DATE]

PREPARED AUTOMATICALLY:
---
1. Deliverables due today [auto-list by owner]
2. Deliverables due in 2 days [auto-list]
3. Active blockers [auto-list]
4. Status changes since yesterday [auto-list of changed items]

STANDUP FORMAT (30 seconds per person):
---
- What did I complete since last standup?
- What will I complete today?
- What is blocking me?

OUTPUTS TO CAPTURE:
---
[ ] New blockers opened
[ ] Deliverables marked complete
[ ] Escalations triggered if needed
```

#### When to Activate Daily Standup

- Coverage owner or project owner declares a "hot workstream"
- PM go-live within 5 business days
- Critical RiskBlocker opened with < 48-hour resolution window
- Production incident affecting a live PM

---

### 2.4 Weekly Operating Review

**Cadence:** Weekly
**Duration:** 45–60 minutes
**Participants:** Business-side PMO lead, coverage owners, business leadership, optional tech leads

#### Required Inputs

- All active Projects (status, health, owner, target_date)
- All Milestones with target_date in next 14 days
- All overdue Deliverables (past due_date, not complete)
- All PMCoverageRecords with health != `green`
- All open RiskBlockers ordered by severity and age
- All open Decisions ordered by urgency and age

#### Auto-Generated Prep (system produces)

- Full operating review agenda (see Workflow 1.4 template)
- Count of overdue deliverables, at-risk PMs, open blockers by severity
- Milestones due in next 14 days (milestone calendar)
- Decisions pending with age and urgency

#### Meeting Template / Checklist

```
WEEKLY OPERATING REVIEW — [DATE]
Generated: [timestamp] | Prep time target: <15 min

===== CRITICAL ITEMS =====
[auto: Decisions blocking milestones or > 7 days pending]
[auto: PMCoverageRecords with health = red]
[auto: Milestones missed this week]

===== OPERATING DASHBOARD =====
Active projects:     [count]
PMs in onboarding:   [count]  |  At risk (yellow/red): [count]
Overdue deliverables: [count]
Open blockers:        [count] ([critical count] critical, [high count] high)
Pending decisions:    [count]

===== SECTION 1: AT-RISK PMs =====
[auto: PMCoverageRecord list where health != green, with stage, health, blocker count]

===== SECTION 2: OVERDUE DELIVERABLES =====
[auto: Deliverables where due_date < today, not complete, sorted by age desc]

===== SECTION 3: MILESTONE REVIEW =====
Slipped this week: [auto]
Due next 14 days:  [auto: milestone calendar]

===== SECTION 4: BLOCKERS NEEDING ACTION =====
[auto: RiskBlockers where age > severity threshold or escalation_status = pending]

===== SECTION 5: DECISIONS AWAITING ACTION =====
[auto: Decisions ordered by urgency desc, age desc]

===== SECTION 6: REPRIORITIZATION =====
[human: any changes to project priority or resource allocation?]

===== SECTION 7: LEADERSHIP TALKING POINTS =====
[human + auto draft: summary of wins, at-risk items, decisions needed from leadership]

OUTPUTS TO CAPTURE:
---
[ ] Overdue deliverable owners confirmed / dates updated
[ ] Escalations created for stalled blockers
[ ] Priority changes recorded
[ ] Decisions assigned to approvers with deadlines
[ ] StatusUpdates published for all active projects
[ ] Leadership summary drafted
```

#### Data Views Needed

- Operating Review View (see Section 4)
- PM Coverage View (all PMs, health, stage)

---

### 2.5 PM Touchpoint / Relationship Check-In

**Cadence:** Biweekly or monthly per PM (separate from onboarding meeting)
**Duration:** 20–30 minutes
**Participants:** PM, coverage owner
**Purpose:** Ensure PM feels supported and heard; capture emerging needs before they become urgent

#### Required Inputs

- PMCoverageRecord (stage, health, last_touchpoint_date)
- All open PMNeeds for this PM (status, urgency)
- Status of recently closed or in-progress PMNeeds
- PMCoverageRecord.top_open_needs, top_blockers

#### Auto-Generated Prep (system produces)

- PM summary: stage, health, days since last touchpoint
- Open needs summary: count by status, any critical/high urgency
- Recent progress: needs delivered or milestones completed in last 30 days
- Open blockers list

#### Meeting Template / Checklist

```
PM TOUCHPOINT — [PM NAME] — [DATE]

PREPARED AUTOMATICALLY:
---
1. PM snapshot
   Stage: [auto] | Health: [auto] | Last touchpoint: [auto] ([X] days ago)

2. Open needs summary [auto]
   Total open: [count] | Critical/High: [count]
   Top needs: [auto-list of top 3 by urgency]

3. Recent wins [auto: needs delivered or milestones completed in last 30 days]

4. Open blockers [auto: any blockers affecting this PM]

DISCUSSION AGENDA (human-driven):
---
5. PM feedback — how is the PM feeling about support and progress?
6. Current needs check — any existing needs status updates from PM perspective?
7. New asks — any new needs or concerns?
8. Expectations check — is the PM's understanding of timelines accurate?

OUTPUTS TO CAPTURE:
---
[ ] PMCoverageRecord.last_touchpoint_date updated to today
[ ] PMCoverageRecord.health_status updated based on PM sentiment
[ ] New PMNeeds logged
[ ] PMNeed priority adjustments based on PM feedback
[ ] Expectation alignment notes captured in StatusUpdate or PM need notes
```

---

### 2.6 Business–Technology Coordination Meeting

**Cadence:** Weekly
**Duration:** 30–45 minutes
**Participants:** Business-side coverage leads, tech leads (centralized technology), key tech partners
**Purpose:** Bridge business needs into tech priorities; hold tech accountable with visible dates and criteria

#### Required Inputs

- PMNeeds in status `needs_new_project` or `in_progress` with tech dependency
- Projects with tech owner that have delayed milestones
- RiskBlockers with tech-side ownership
- Decisions pending tech input or approval

#### Auto-Generated Prep (system produces)

- PMNeeds awaiting tech action (status = `needs_new_project` or `in_progress`, tech dependency)
- Projects with delayed milestones owned by tech teams
- RiskBlockers with tech owners, sorted by severity
- Pending decisions requiring tech input

#### Meeting Template / Checklist

```
BUSINESS–TECH COORDINATION — [DATE]

PREPARED AUTOMATICALLY:
---
1. PM needs awaiting tech action [auto]
   - [need title] | PM: [name] | Urgency: [urgency] | Age: [days] | Status: [status]

2. Projects with tech delays [auto]
   - [project] | Milestone: [name] | Was due: [date] | Current status: [status]

3. Open tech-owned blockers [auto]
   - [blocker] | Project: [name] | Severity: [sev] | Age: [days]

4. Decisions needing tech input [auto]

DISCUSSION AGENDA (human-driven):
---
5. Priority review — are business priorities clear to tech team?
6. Blocker resolution — what can tech unblock this week?
7. Date commitments — confirm or replan delayed milestones
8. Ownership clarification — any unclear owners on tech-side work?
9. Escalations — flag items that need leadership attention

OUTPUTS TO CAPTURE:
---
[ ] Tech commitments confirmed (deliverable owners + dates updated)
[ ] New blockers opened for unresolved tech delays
[ ] Priority confirmations recorded (Decision if needed)
[ ] Escalations triggered for items leadership must see
[ ] StatusUpdates updated for impacted projects
```

---

### 2.7 Monthly Roadmap / Vision Review

**Cadence:** Monthly
**Duration:** 60–90 minutes
**Participants:** Business leadership, PMO lead, tech leadership, PM coverage leads
**Purpose:** Ensure execution is advancing the right longer-term platform; realign priorities across three horizons

#### Required Inputs

- All active Projects (by type, horizon, status)
- PMNeed category distribution and trend (last 90 days)
- PM pipeline: PMs in each onboarding stage
- Capability gaps (clustered PM needs without delivery path)
- RiskBlockers trending: most common categories
- Delivery bottlenecks: teams with most overdue items

#### Auto-Generated Prep (system produces)

- Projects by horizon (short/medium/long-term) and health
- PM pipeline summary (count by stage, go-live targets)
- Top 5 most-requested unmet PM needs
- Top capability gaps by PM impact count
- Current delivery bottlenecks by team/area

#### Meeting Template / Checklist

```
MONTHLY ROADMAP REVIEW — [MONTH YEAR]

PREPARED AUTOMATICALLY:
---
1. PM pipeline summary [auto]
   Pipeline: [count] | Pre-start: [count] | In onboarding: [count]
   Live: [count] | Stabilization: [count] | Steady state: [count]
   Upcoming go-lives: [auto-list with dates]

2. Project portfolio by horizon [auto]
   Short-term: [count active, count at risk]
   Medium-term: [count active, count at risk]
   Long-term: [count active, count at risk]

3. Top unmet PM needs (last 90 days) [auto: top 5 by frequency]
   - [need cluster] | [count of PMs requesting] | [capability gap Y/N]

4. Top capability gaps [auto]
   - [capability area] | [# PMs blocked] | [delivery status]

5. Delivery bottlenecks [auto: teams/areas with most overdue items]

DISCUSSION AGENDA (human-driven):
---
6. Horizon check — are we investing appropriately across short/medium/long-term?
7. Capability roadmap — which gaps do we commit to closing this quarter?
8. PM priorities — any shifts in PM onboarding sequence or priority?
9. Re-scoping decisions — what needs to change given current delivery capacity?
10. Leadership requests — what do we need from leadership to unblock?

OUTPUTS TO CAPTURE:
---
[ ] Roadmap adjustments documented (Decision records)
[ ] Capability reprioritization captured
[ ] PM onboarding sequence updated if changed
[ ] New projects created for approved capability builds
[ ] Requests for leadership support formalized
[ ] StatusUpdate (initiative-level) published
```

---

### 2.8 Milestone Readiness Review

**Cadence:** Ad hoc, 1–2 weeks before a major milestone
**Duration:** 30–45 minutes
**Participants:** Milestone owner, coverage owner, key delivery stakeholders
**Purpose:** Validate readiness against explicit criteria before approving milestone completion

#### Required Inputs

- Milestone (acceptance_criteria, gating_conditions, target_date, confidence)
- All Deliverables linked to this milestone (status, owner, due_date)
- Open RiskBlockers impacting this milestone
- Open Decisions impacting this milestone

#### Auto-Generated Prep (system produces)

- Milestone acceptance criteria checklist
- Deliverable completion rate for this milestone (X of Y complete)
- Open blockers linked to milestone
- Pending decisions linked to milestone
- Confidence score

#### Meeting Template / Checklist

```
MILESTONE READINESS REVIEW — [MILESTONE NAME] — [DATE]
Target date: [date] | Confidence: [score]

PREPARED AUTOMATICALLY:
---
1. Acceptance criteria checklist [auto from milestone.acceptance_criteria]
   [ ] [criterion 1]
   [ ] [criterion 2]
   ...

2. Deliverable completion [auto]
   Complete: [X] / [Y] | Overdue: [count] | Not started: [count]
   Incomplete deliverables: [auto-list with owner and due date]

3. Open blockers [auto]
   - [blocker] | Severity: [sev] | Age: [days] | Owner: [name]

4. Pending decisions [auto]

READINESS VOTE (human decision):
---
[ ] Go — all criteria met, milestone ready to close
[ ] Conditional Go — minor gaps, specific items must complete by [date]
[ ] No Go — significant gaps, milestone date must move

OUTPUTS TO CAPTURE:
---
[ ] Milestone status updated (complete / at risk / replanned)
[ ] If Go: milestone closed, next milestone activated
[ ] If Conditional Go: gap list created as Deliverables with hard deadlines
[ ] If No Go: new target date set, RiskBlocker opened, StatusUpdate published
[ ] Confidence score updated
[ ] PMCoverageRecord health updated if onboarding milestone
```

---

### 2.9 Risk / Blocker Escalation Review

**Cadence:** Weekly (or as part of operating review)
**Duration:** 20–30 minutes
**Participants:** Coverage owner, escalation owners, relevant project/tech leads
**Purpose:** Resolve stuck items; force clarity on who owns resolution and by when

#### Required Inputs

- All open RiskBlockers ordered by severity, then age
- Blockers that have exceeded age threshold without resolution
- Blockers with no assigned owner
- Decisions that are blocking open RiskBlockers

#### Auto-Generated Prep (system produces)

- Blockers past age threshold by severity
- Blockers with no owner (or owner changed recently)
- Blockers with no recent update (> 5 days)
- Decisions pending that are blocking resolution

#### Meeting Template / Checklist

```
RISK / BLOCKER ESCALATION REVIEW — [DATE]

PREPARED AUTOMATICALLY:
---
1. Blockers past age threshold [auto by severity]
   Critical (>1d): [list]
   High (>3d): [list]
   Medium (>7d): [list]

2. Blockers with no owner [auto]
3. Blockers with no update in 5+ days [auto]
4. Decisions blocking resolution [auto]

DISCUSSION AGENDA (human-driven):
---
5. For each critical/high blocker: who owns resolution? What is the path?
6. Assign owners to unowned blockers (none leave unassigned)
7. Set resolution deadlines — every blocker gets a next action date
8. Identify decisions needed — convert ambiguous blockers to Decision records
9. Escalate to leadership if resolution requires senior support

OUTPUTS TO CAPTURE:
---
[ ] Every blocker has an owner and a next action date
[ ] Stale blockers have updated resolution paths
[ ] New Decision records created for blockers needing choices
[ ] Escalation status updated for items going to leadership
[ ] If resolution agreed: RiskBlocker.resolution_date set, status → pending_resolution
[ ] StatusUpdates published for impacted projects
```

---

### 2.10 Post-Go-Live Stabilization Review

**Cadence:** Weekly for 2–6 weeks post-go-live
**Duration:** 20–30 minutes
**Participants:** PM (or PM team lead), coverage owner, operations / support leads
**Purpose:** Confirm the PM is genuinely functional; capture early issues; determine when to close stabilization

#### Required Inputs

- PMCoverageRecord (stage = `live` or `stabilization`)
- Stabilization checklist (Deliverable list)
- Open RiskBlockers or PMNeeds opened post-go-live
- PM feedback / sentiment

#### Auto-Generated Prep (system produces)

- Stabilization checklist completion rate
- Issues opened since go-live (RiskBlockers + new PMNeeds)
- Days since go-live
- PM health status

#### Meeting Template / Checklist

```
POST-GO-LIVE STABILIZATION REVIEW — [PM NAME] — [DATE]
Days since go-live: [auto] | Stage: [auto] | Health: [auto]

PREPARED AUTOMATICALLY:
---
1. Stabilization checklist progress [auto]
   Complete: [X] / [Y] | Remaining: [list]

2. Issues opened since go-live [auto]
   RiskBlockers: [count] | New PM Needs: [count]
   Open critical/high: [auto-list]

DISCUSSION AGENDA (human-driven):
---
3. PM feedback — what is working? What is not?
4. Issue triage — support issue or roadmap item?
5. Checklist items — confirm any that are done but not marked
6. Closure check — is PM ready to move to steady state?

OUTPUTS TO CAPTURE:
---
[ ] Stabilization checklist items updated
[ ] New issues logged (RiskBlocker or PMNeed)
[ ] Issues triaged as support vs roadmap
[ ] PMCoverageRecord.health_status updated
[ ] If closure ready: PMCoverageRecord.stage → steady_state, project archived
[ ] Closure StatusUpdate published
```

---

## 3. Artifact Lifecycle Rules

### 3.1 PMCoverageRecord State Machine

```
                    [backwards allowed for failed UAT or gate failure]
                    ←──────────────────────────────
pipeline → pre_start → requirements_discovery → onboarding_in_progress → uat
  → go_live_ready → live → stabilization → steady_state
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `pipeline` | pm_name, team_or_pod, coverage_owner |
| `pre_start` | + go_live_target_date, strategy_type, region |
| `requirements_discovery` | + onboarding project linked |
| `onboarding_in_progress` | + at least 1 PMNeed captured, all milestones seeded |
| `uat` | + UAT Complete milestone has acceptance criteria |
| `go_live_ready` | + all pre-go-live milestones complete, no critical/high blockers |
| `live` | + PM Live milestone marked complete |
| `stabilization` | + stabilization checklist activated |
| `steady_state` | + stabilization checklist complete, no critical/high blockers |

**Valid backwards transitions:**
- `uat → onboarding_in_progress`: UAT failed; issues converted to PMNeeds
- `go_live_ready → onboarding_in_progress`: Gate review failed; gap list created

**Archival rule:** PMCoverageRecord is never deleted. When `steady_state`, project is archived but PMCoverageRecord remains active for ongoing support.

---

### 3.2 PMNeed State Machine

```
new → triaged → [mapped_to_existing_capability | needs_new_project]
  → in_progress → [delivered | deferred | cancelled]
           ↓
         blocked → in_progress (when unblocked)
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `new` | title, pm_id, category, urgency, requested_by, date_raised |
| `triaged` | + business_rationale, urgency confirmed, triage date |
| `mapped_to_existing_capability` | + mapped_capability_id or linked_project_ids |
| `needs_new_project` | + resolution_path documented |
| `in_progress` | + linked_project_ids with active project, owner assigned |
| `blocked` | + linked RiskBlocker, escalation owner |
| `delivered` | + resolution summary, PM acknowledged |
| `deferred` | + deferral rationale, expected timeframe, PM informed |
| `cancelled` | + cancellation rationale |

**Archival rule:** PMNeeds are never deleted. `delivered`, `deferred`, and `cancelled` needs are retained for pattern analysis and capability planning.

---

### 3.3 Project State Machine

```
draft → active → [at_risk | blocked] → active (when resolved)
       → completed → archived
       → cancelled
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `draft` | name, project_type, business_objective, owner |
| `active` | + start_date, target_date, success_criteria, linked_pm_needs (at least 1), linked_milestones (at least 1) |
| `at_risk` | + linked RiskBlocker with severity and owner |
| `blocked` | + RiskBlocker escalation_status = escalated |
| `completed` | + all milestones complete, acceptance confirmed by business side |
| `archived` | + StatusUpdate published with closure summary |
| `cancelled` | + cancellation rationale, linked PMNeeds updated |

**Naming convention:** `[Type] - [PM or Capability] - [Short Outcome]`

**Archival rule:** Completed projects archived in Asana (not deleted). Archive date recorded. Accessible for historical query.

---

### 3.4 Milestone State Machine

```
not_started → in_progress → [at_risk | blocked] → in_progress
           → complete
           → skipped (with rationale)
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `not_started` | name, project_id, target_date, owner |
| `in_progress` | + gating_conditions, confidence set |
| `at_risk` | + confidence = `low`, linked RiskBlocker |
| `blocked` | + linked RiskBlocker severity = high or critical |
| `complete` | + acceptance_criteria validated, completion_date recorded |
| `skipped` | + rationale, approved by coverage owner |

**Naming convention:** `[PM or Project] - [Checkpoint]`

**Gate rule:** A milestone cannot move to `complete` without all gating_conditions confirmed. Coverage owner must confirm, not just the task owner.

---

### 3.5 Deliverable State Machine

```
not_started → in_progress → [blocked] → in_progress
           → complete
           → cancelled (with rationale)
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `not_started` | title, project_id, owner, due_date |
| `in_progress` | + last_updated |
| `blocked` | + blocked_by (linked RiskBlocker or dependency), notes |
| `complete` | + completion confirmed, last_updated |
| `cancelled` | + rationale in notes |

**Ownership rule:** Every deliverable must have a single named human owner. "Team" or "TBD" are not valid owners in `active` state.

**Staleness rule:** Deliverables not updated in > 7 days flagged as stale; coverage owner alerted.

---

### 3.6 RiskBlocker State Machine

```
open → [escalated] → pending_resolution → resolved
     → wont_fix (with rationale)
     → accepted (risk accepted, monitoring continues)
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `open` | title, type, severity, owner, date_opened, impacted_project_ids |
| `escalated` | + escalation_status = `escalated`, escalation owner |
| `pending_resolution` | + mitigation_plan, resolution_date (expected) |
| `resolved` | + resolution_date (actual), resolution summary |
| `wont_fix` | + rationale, approved by coverage owner |
| `accepted` | + acceptance rationale, review_date |

**Naming convention:** `[Scope] - [Short Problem]`

**Auto-escalation rule:** If RiskBlocker stays in `open` beyond age threshold (see Section 1.5), system alerts coverage owner and increases severity one level.

---

### 3.7 Decision State Machine

```
pending → [under_review] → decided → implemented
        → deferred (with expected date)
        → cancelled
```

**Required fields by state:**

| State | Required Fields |
|-------|----------------|
| `pending` | title, context, options_considered, approver(s) |
| `under_review` | + discussion notes, deadline |
| `decided` | + chosen_path, rationale, decision_date, approver(s) confirmed |
| `implemented` | + implementation confirmation, impacted_artifacts updated |
| `deferred` | + deferral rationale, expected_decision_date |
| `cancelled` | + cancellation rationale |

**Aging rule:** Decisions pending > 7 business days without movement trigger alert to coverage owner and appear in weekly operating review.

**Immutability rule:** Once a Decision is `decided`, it cannot be deleted. Only superseded by a new Decision record that references the prior one.

---

### 3.8 StatusUpdate Rules

StatusUpdates are append-only snapshots. They are never edited after publishing.

**Required fields:**
- `scope_type` (`project`, `pm`, `initiative`)
- `scope_id`
- `overall_status` (`green`, `yellow`, `red`)
- `what_changed_this_period`
- `next_key_milestones`
- `top_blockers`
- `updated_by`
- `updated_at`

**Cadence rules:**
- All active projects: at minimum weekly StatusUpdate
- At-risk projects (health = yellow/red): StatusUpdate after every significant change
- PM-level updates: after every PM Onboarding Meeting and PM Touchpoint
- Initiative-level updates: after every monthly roadmap review

---

## 4. Dashboard / Reporting Requirements

### 4.1 PM View

**Purpose:** Single-PM deep dive; used in PM onboarding meetings and touchpoints

**Data sources:**
- PMCoverageRecord (1 record)
- PMNeed (filtered to this PM)
- Project (filtered to linked_project_ids)
- Milestone (filtered to projects linked to this PM)
- RiskBlocker (filtered to impacted_pm_ids)
- StatusUpdate (filtered to this PM's scope_ids)

**Required display elements:**

| Element | Source | Description |
|---------|--------|-------------|
| PM stage | PMCoverageRecord.onboarding_stage | Current stage with visual indicator |
| Health status | PMCoverageRecord.health_status | Green / Yellow / Red with last updated date |
| Go-live target | PMCoverageRecord.go_live_target_date | Date + days remaining |
| Days since last touchpoint | PMCoverageRecord.last_touchpoint_date | Alert if > 14 days |
| Milestone progress | Milestone list for this PM | X of Y complete; next milestone with date |
| Open needs by status | PMNeed list | Count and list by status; highlight critical/high |
| Open blockers | RiskBlocker list | Sorted by severity; highlight aged items |
| Linked projects | Project list | Name, status, health for each |
| Recent status update | StatusUpdate | Last PM-level update content |

**Refresh cadence:** Real-time (on demand in Asana); sidecar digest refreshed daily.

---

### 4.2 Project View

**Purpose:** Single-project deep dive; used in project working sessions

**Data sources:**
- Project (1 record)
- Milestone (filtered to project_id)
- Deliverable (filtered to project_id)
- RiskBlocker (filtered to impacted_project_ids)
- Decision (filtered to impacted_artifacts)
- StatusUpdate (filtered to this project)
- Dependency (filtered to project)

**Required display elements:**

| Element | Source | Description |
|---------|--------|-------------|
| Project health | Project.status + latest StatusUpdate.overall_status | Visual RAG status |
| Business objective | Project.business_objective | One-line summary |
| Days to target | Project.target_date | Days remaining + trend |
| Success criteria | Project.success_criteria | Explicit criteria list |
| Milestone timeline | Milestone list | Gantt-style or list; status + confidence + target date |
| Overdue deliverables | Deliverable where due_date < today, status != complete | List with owner + age |
| Upcoming deliverables | Deliverable where due_date in next 7 days | List with owner |
| Open blockers | RiskBlocker list | Sorted by severity |
| Pending decisions | Decision list | Sorted by urgency + age |
| Dependencies | Dependency list | External dependencies and status |
| Linked PM needs | PMNeed list | Needs this project is fulfilling |

**Refresh cadence:** Real-time in Asana; sidecar daily digest.

---

### 4.3 Operating Review View

**Purpose:** Cross-portfolio command view; used in weekly operating review

**Data sources:**
- All active Projects
- All active PMCoverageRecords
- All open RiskBlockers
- All open Decisions
- All Milestones with target_date in next 14 days
- All Deliverables overdue

**Required display elements:**

| Element | Source | Description |
|---------|--------|-------------|
| Portfolio health summary | All Projects | Count by status: green/yellow/red |
| PM pipeline | All PMCoverageRecords | Count by stage; at-risk count |
| Overdue deliverables | Deliverable where due_date < today | Total count; list by age |
| Milestone slips this week | Milestone where target_date changed or missed this week | List with impact |
| Milestone calendar (14 days) | Milestones where target_date between today and +14d | Calendar or list view |
| Open blockers by severity | RiskBlocker grouped by severity | Count per severity; list critical/high |
| Aged blockers | RiskBlocker where age > threshold | Alert list |
| Pending decisions | Decision where status = pending | List by urgency + age |
| Weekly wins | Deliverables + milestones completed last 7 days | Brief list |

**Refresh cadence:** Daily automated digest; live view on demand.

---

### 4.4 Roadmap View

**Purpose:** Strategic portfolio view; used in monthly roadmap / vision review

**Data sources:**
- All Projects (grouped by horizon/type)
- All PMCoverageRecords (pipeline view)
- PMNeed (trend analysis, category distribution)
- RiskBlocker (recurring categories, bottleneck teams)

**Required display elements:**

| Element | Source | Description |
|---------|--------|-------------|
| Projects by horizon | Project.horizon (short/medium/long-term) | Count and health per horizon |
| PM pipeline funnel | PMCoverageRecord by stage | Stage-by-stage count; upcoming go-lives |
| Top unmet PM need clusters | PMNeed category distribution (last 90 days) | Top 5 most-requested, undelivered categories |
| Delivery bottlenecks | Deliverables grouped by owner team | Teams with most overdue or blocked items |
| Capability gap summary | PMNeed without linked capability or project | Unmet needs without delivery path |

**Refresh cadence:** Weekly; full refresh before monthly roadmap meeting.

---

### 4.5 Executive Summary View

**Purpose:** Leadership-level snapshot; minimal detail, maximum signal

**Data sources:**
- PMCoverageRecord (stage and health)
- Milestone (go-live targets)
- RiskBlocker (critical/high severity, leadership-escalated)
- Decision (pending, leadership-level)
- Project (health summary)

**Required display elements:**

| Element | Source | Description |
|---------|--------|-------------|
| PM onboarding summary | PMCoverageRecord by stage | PMs in pipeline / onboarding / live / steady-state |
| Upcoming go-lives | PMCoverageRecord where go_live_target_date in next 60 days | PM name, target date, health |
| Go-live at risk | PMCoverageRecord where health = yellow/red and stage != steady_state | PM name, stage, top blocker |
| Critical blockers | RiskBlocker where severity = critical or escalation_status = escalated | Title, impacted PM/project, age |
| Decisions requiring leadership | Decision where approver is leadership and status = pending | Title, context, age, urgency |
| Capability constraints | Top 3 capability gaps by PM impact | Capability name, PM count affected |

**Refresh cadence:** Weekly; always available on demand. Ideally auto-generated as a PDF/message summary.

---

## 5. Bot Use Case Specifications

### Design Principles

All bot commands must:
1. Route through templates — never create free-form records
2. Require mandatory fields before writing — validate before creating
3. Summarize before writing for high-impact actions — show preview, confirm
4. Log all actions — create audit trail
5. Return links — always return Asana URL + sidecar record ID for created items
6. Fail safely — never partially create objects; roll back if incomplete

---

### Query Commands (Read-Only)

#### BOT-Q1: "What's the status of PM [name]?"

**Trigger phrase:** `status of PM [name]`, `how is PM [name] doing`

**Input parameters:**
- `pm_name` (required) — matched against PMCoverageRecord.pm_name

**Output format:**
```
PM STATUS: [PM Name]
─────────────────────────────
Stage:           [stage]
Health:          [GREEN / YELLOW / RED]
Go-live target:  [date] ([X] days away)
Last touchpoint: [date] ([X] days ago)

Next milestone:  [milestone name] → [target date] (confidence: [level])

Top open needs ([count] total):
  • [need 1] | [status] | [urgency]
  • [need 2] | [status] | [urgency]

Top blockers ([count] total):
  • [blocker 1] | [severity] | [age] days

Linked projects: [count] active
[Asana link to PM Coverage Record]
```

**Data sources queried:** PMCoverageRecord, PMNeed (top 3 by urgency), Milestone (next incomplete), RiskBlocker (top 3 by severity)

**Safety rules:** Read-only. No writes. PM name must match exactly or return top-3 closest matches for confirmation.

---

#### BOT-Q2: "What's blocking Project [name]?"

**Trigger phrase:** `blocking [project]`, `what's delaying [project]`

**Input parameters:**
- `project_name` (required)

**Output format:**
```
BLOCKERS FOR: [Project Name]
─────────────────────────────
Overall health: [status]
Target date:    [date]

Open blockers ([count]):
  [CRITICAL] [blocker title] | Owner: [name] | Age: [X] days
  [HIGH]     [blocker title] | Owner: [name] | Age: [X] days
  ...

Pending decisions blocking progress:
  • [decision title] | Waiting on: [approver] | Age: [X] days

At-risk milestones:
  • [milestone] | Target: [date] | Confidence: [level]

[Asana project link]
```

**Data sources queried:** Project, RiskBlocker (impacted_project_ids), Decision, Milestone (at_risk status)

**Safety rules:** Read-only.

---

#### BOT-Q3: "What's at risk this week?"

**Trigger phrase:** `at risk this week`, `what's at risk`, `weekly risk summary`

**Output format:**
```
WEEKLY RISK SUMMARY — [DATE]
─────────────────────────────
At-risk PMs ([count]):
  • [PM name] | Stage: [stage] | Health: [status] | Top blocker: [blocker]

Milestone slips this week ([count]):
  • [milestone] | Project: [name] | Slipped from: [date] → [new date]

Overdue deliverables ([count]):
  • [deliverable] | Owner: [name] | [X] days overdue | Project: [name]

Critical/high blockers ([count]):
  [CRITICAL] [blocker] | Owner: [name] | Age: [X] days
  [HIGH] ...

[Link to Operating Review View]
```

**Data sources queried:** PMCoverageRecord (health != green), Milestone (slipped), Deliverable (overdue), RiskBlocker (critical/high)

**Safety rules:** Read-only.

---

#### BOT-Q4: "What decisions are pending?"

**Trigger phrase:** `decisions pending`, `what decisions are waiting`

**Output format:**
```
PENDING DECISIONS — [DATE]
─────────────────────────────
[count] decisions awaiting action

[URGENT] [decision title]
  Waiting on: [approver] | Age: [X] days
  Impacts: [PM/project name]

[HIGH] [decision title]
  ...

Oldest pending: [decision title] — [X] days
[Link to full decision list]
```

**Data sources queried:** Decision (status = pending), ordered by urgency desc, age desc

**Safety rules:** Read-only.

---

#### BOT-Q5: "Show open PM needs for [PM name / region / category]"

**Trigger phrase:** `open needs for [PM/region/category]`

**Input parameters:**
- `pm_name` OR `region` OR `category` (at least one required)

**Output format:**
```
OPEN PM NEEDS — [filter description]
─────────────────────────────
Total open: [count] | Critical: [count] | High: [count]

[CRITICAL] [need title] | PM: [name] | Category: [cat] | Age: [X] days | Status: [status]
[HIGH]     ...
...

[Link to PM Needs project in Asana]
```

**Data sources queried:** PMNeed (filtered by pm_id, region, or category; status not in delivered/cancelled)

**Safety rules:** Read-only.

---

#### BOT-Q6: "What capability gaps are coming up most often?"

**Trigger phrase:** `capability gaps`, `most common PM needs`, `repeated asks`

**Output format:**
```
CAPABILITY GAP ANALYSIS — [DATE RANGE]
─────────────────────────────
Based on PM needs in the last [90] days

Rank | Category | Need Count | PMs Affected | Has Delivery Path?
  1  | [cat]    | [count]    | [count]      | [Yes/No]
  2  | [cat]    | [count]    | [count]      | [Yes/No]
  ...

Top 3 unmet needs without delivery path:
  • [need cluster] | [count] PMs | [urgency level]

[Link to Roadmap View]
```

**Data sources queried:** PMNeed (category distribution, status analysis, linked_project_ids), last 90 days

**Safety rules:** Read-only.

---

### Create Commands (Write — Require Confirmation)

#### BOT-C1: "Create a new PM onboarding project for [PM name]"

**Trigger phrase:** `create onboarding project for [PM]`, `new PM onboarding [PM]`

**Input collection (bot prompts user for each):**
1. PM name (required)
2. Team / pod (required)
3. Strategy type (required)
4. Region (required)
5. Coverage owner (required — must be a valid user)
6. Go-live target date (required)

**Validation:**
- No duplicate PMCoverageRecord for same PM name
- Go-live target date must be > 30 days in future
- Coverage owner must be a known user

**Preview shown before write:**
```
CONFIRM NEW ONBOARDING PROJECT:
PM: [name] | Team: [team] | Region: [region]
Coverage owner: [name] | Go-live target: [date]

Will create:
  ✓ PM Coverage Record (stage: pre_start)
  ✓ Onboarding project from template
  ✓ 10 default milestones (dates auto-calculated from go-live target)
  ✓ PM Needs intake checklist

Confirm? (yes / no / edit)
```

**On confirm — objects created:**
1. PMCoverageRecord (stage: `pre_start`)
2. Asana Project from onboarding template
3. 10 Milestones with calculated target dates
4. Intake checklist Deliverables (kickoff checklist)

**Output:**
```
ONBOARDING PROJECT CREATED
PM: [name]
Asana project: [link]
PM Coverage Record: [link]
Go-live target: [date]
Milestones seeded: 10

Next step: Schedule kickoff and capture PM needs.
[Asana project link]
```

**Audit log entry:** `CREATE | onboarding_project | PM:[name] | by:[user] | at:[timestamp]`

---

#### BOT-C2: "Log a new PM need for [PM name]"

**Trigger phrase:** `log PM need for [PM]`, `new need for [PM]`

**Input collection:**
1. PM name (required — must match existing PMCoverageRecord)
2. Need title (required)
3. Category (required — must be from defined list)
4. Urgency (required — `critical`, `high`, `medium`, `low`)
5. Business rationale (required — minimum 20 characters)
6. Requested by (required)
7. Desired by date (optional)

**Validation:**
- PM must have active PMCoverageRecord
- Duplicate detection: warn if similar title exists for same PM
- Business rationale cannot be empty

**Preview shown before write:**
```
CONFIRM NEW PM NEED:
PM: [name] | Category: [cat] | Urgency: [urgency]
Title: [title]
Rationale: [rationale]
Requested by: [name] | Desired by: [date or "not specified"]

Confirm? (yes / no / edit)
```

**On confirm:**
1. PMNeed created (status: `new`)
2. PMCoverageRecord.top_open_needs updated
3. Triage alert sent to coverage owner

**Output:**
```
PM NEED LOGGED
Title: [title] | PM: [name]
Status: new | Urgency: [urgency]
Asana task: [link]

Next step: Triage and route within 1 business day.
```

**Audit log entry:** `CREATE | pm_need | PM:[name] | title:[title] | by:[user] | at:[timestamp]`

---

#### BOT-C3: "Open a blocker on [project name]"

**Trigger phrase:** `open blocker on [project]`, `log blocker for [project]`

**Input collection:**
1. Project name (required — must match active Project)
2. Blocker title (required)
3. Type (required — `risk`, `blocker`, `issue`)
4. Severity (required — `critical`, `high`, `medium`, `low`)
5. Impacted PM (optional — auto-populated if project linked to PM)
6. Impacted milestone (optional)
7. Owner (required)
8. Mitigation plan (optional but prompted)

**Validation:**
- Project must be active
- Severity must be specified — cannot default to `medium` for `critical`/`high` items without confirmation
- Owner must be a known user

**Preview before write:** Standard preview pattern.

**On confirm:**
1. RiskBlocker created (status: `open`)
2. Linked to project, PM (if provided), milestone (if provided)
3. Project health updated to `yellow` (if severity high/critical)
4. Coverage owner alerted

**Output:**
```
BLOCKER OPENED
Title: [title] | Project: [project]
Severity: [sev] | Type: [type] | Owner: [name]
Asana task: [link]

[If severity = critical]: CRITICAL blocker — coverage owner alerted.
```

**Audit log entry:** `CREATE | risk_blocker | project:[name] | severity:[sev] | by:[user] | at:[timestamp]`

---

#### BOT-C4: "Create a milestone readiness review task"

**Trigger phrase:** `create milestone readiness review for [milestone]`

**Input collection:**
1. Milestone name (required — must match active Milestone)
2. Review date (required — should be 7–14 days before milestone target date)
3. Assigned to (required)

**On confirm:**
1. Deliverable created: "Milestone Readiness Review — [milestone name]"
2. Milestone Readiness Review template checklist attached
3. Linked to milestone and project
4. Reminder set for review date

**Output:**
```
MILESTONE READINESS REVIEW CREATED
Milestone: [name] | Target: [milestone date]
Review date: [review date] | Assigned to: [name]
Asana task: [link]
```

---

#### BOT-C5: "Create this month's roadmap review agenda"

**Trigger phrase:** `roadmap review agenda`, `create monthly roadmap agenda`

**Input collection:** None required (auto-generated from current state)

**Auto-generates:**
- PM pipeline snapshot (current counts by stage)
- Project portfolio by horizon
- Top 5 unmet PM need clusters (last 90 days)
- Top capability gaps
- Delivery bottlenecks

**On confirm:**
1. Asana task created with agenda content
2. Task linked to roadmap review recurring project (if exists)
3. Agenda shared with meeting participants

---

### Update Commands (Write — Require Confirmation)

#### BOT-U1: "Mark this blocker escalated"

**Trigger phrase:** `escalate blocker [blocker title / ID]`, `mark [blocker] escalated`

**Input parameters:**
- Blocker identifier (required — title or Asana task ID)
- Escalation owner (required)

**Validation:**
- Blocker must be in `open` status
- Escalation owner must be different from current owner (or confirm if same)

**Preview:**
```
CONFIRM ESCALATION:
Blocker: [title]
Current owner: [name] | Escalation owner: [name]
Status will change: open → escalated

Confirm? (yes / no)
```

**On confirm:**
1. RiskBlocker.escalation_status = `escalated`
2. Escalation owner notified
3. StatusUpdate triggered for impacted project

---

#### BOT-U2: "Move PM [name] to [stage]"

**Trigger phrase:** `move PM [name] to [stage]`, `update PM [name] stage to [stage]`

**Input parameters:**
- PM name (required)
- New stage (required — must be valid transition from current stage)

**Validation:**
- Transition must be valid per state machine
- If advancing to `go_live_ready`: check all pre-go-live milestones are complete; warn if not
- If advancing to `live`: require confirmation that PM Live milestone is marked complete

**Preview:**
```
CONFIRM PM STAGE UPDATE:
PM: [name]
Current stage: [stage] → New stage: [stage]
[If advancing to go_live_ready]: Warning — [X] pre-go-live milestones not yet complete.

Confirm? (yes / no)
```

---

#### BOT-U3: "Update health to [status] for Project [name]"

**Trigger phrase:** `update health [project] to [green/yellow/red]`

**Input parameters:**
- Project name (required)
- New health status (required — `green`, `yellow`, `red`)
- Reason (required if changing to `yellow` or `red`)

**On confirm:**
1. Project health updated
2. If `red`: coverage owner alerted, escalation recommended
3. StatusUpdate draft created with health change and reason

---

#### BOT-U4: "Add a decision record for [topic]"

**Trigger phrase:** `add decision for [topic]`, `log decision about [topic]`

**Input collection:**
1. Title (required)
2. Context (required — what situation prompted this decision)
3. Options considered (required — at least 2)
4. Approver(s) (required — named individuals)
5. Linked PM or project (required)
6. Urgency (required)

**On confirm:**
1. Decision created (status: `pending`)
2. Approver(s) notified
3. Linked to project and/or PM
4. Surfaced in next operating review agenda

---

### Safety and Validation Rules Summary

| Rule | Detail |
|------|--------|
| No orphan creates | Every created object must link to a PM, Project, or Milestone |
| Preview before high-impact writes | Any create action with type = `project` or update affecting `stage` or `health` must show preview |
| Required fields enforced | Bot will not write without mandatory fields; prompts user if missing |
| Duplicate detection | PM names and project names checked for near-matches before create |
| Valid state transitions only | Stage and status changes validated against state machine before accepting |
| Single owner rule | Every Deliverable and RiskBlocker must have a single named owner before save |
| Audit log on every write | `CREATE` or `UPDATE` logged with user, timestamp, object type, and key field values |
| Read-only commands never write | Query commands have no write path |
| Rollback on partial failure | If multi-step create (e.g., onboarding project) fails mid-way, all partial writes rolled back |

---

## Appendix A: v1 vs v2 Feature Boundary

| Feature | v1 (this document) | v2 (later) |
|---------|-------------------|------------|
| PM Coverage Record | Yes (Asana task or sidecar) | Richer with full history |
| PM Need intake and routing | Yes | Capability clustering automation |
| Project + Milestone + Deliverable | Yes (Asana native) | — |
| RiskBlocker tracking | Yes | Heatmaps, aging alerts |
| Decision registry | Yes (lightweight) | Searchable, linked to audit log |
| StatusUpdate | Yes (Asana native) | Auto-generated summaries |
| Capability object | No (clusters only) | Yes (full capability model) |
| Initiative object | No | Yes (portfolio view) |
| Dependency graph | Partial (Asana native) | Full cross-project dependency model |
| Bot — query commands | Phase 3 | — |
| Bot — create commands | Phase 3 (guarded) | Autonomous flows |
| Bot — update commands | Phase 3 (guarded) | — |
| Daily digest | Phase 2 | — |
| Auto-agenda generation | Phase 2 | — |
| Milestone watch alerts | Phase 2 | — |
| Stakeholder Map | No | v2 |
| Advanced analytics | No | Phase 4 |

---

## Appendix B: Naming Convention Quick Reference

| Object Type | Pattern | Example |
|------------|---------|---------|
| Project | `[Type] - [PM or Capability] - [Short Outcome]` | `Onboarding - PM Jane Doe - US Equities Launch` |
| Milestone | `[PM or Project] - [Checkpoint]` | `PM Jane Doe - Go Live Ready` |
| PM Need | `[PM] - [Category] - [Short Need]` | `Jane Doe - Execution - DMA via Goldman` |
| RiskBlocker | `[Scope] - [Short Problem]` | `PM Jane Doe - Historical Data Feed Delayed` |
| Decision | `[Scope] - [Decision Topic]` | `PM Jane Doe - Broker Selection` |
| StatusUpdate | Auto-titled: `[Scope] Status - [Date]` | `PM Jane Doe Status - 2026-03-01` |

---

## Appendix C: Mandatory Field Reference (v1 PM Need Intake)

Minimum required fields when logging a new PM Need (via bot or Asana form):

1. `pm_id` — which PM/team this is for
2. `title` — short, specific description
3. `category` — from defined category list
4. `urgency` — critical / high / medium / low
5. `business_rationale` — minimum one sentence explaining business impact
6. `requested_by` — person who raised this
7. `date_raised` — auto-populated

No PM Need should be accepted without these 7 fields.
