# BAM Systematic Execution Operating System

## Product + Architecture Handoff for Initial Build

## Purpose

Build a business-side execution platform for **BAM Systematic** that makes PM onboarding, platform buildout, and cross-functional delivery **visible, structured, accountable, and scalable**.

This system should use **Asana as the system of record for execution** and add an optional **automation / agent layer** on top (Python service + chat integrations) so that business users can:

* track PM needs clearly,
* convert needs into executable projects,
* monitor milestones, blockers, and decisions,
* coordinate with centralized technology,
* run recurring operating cadences,
* and query project / PM status conversationally.

This is **not** just a task tracker. It is a business execution system for a fast-growing systematic trading business.

This design is grounded in the role as described in the interview transcripts:

* BAM Systematic is trying to support three horizons at once: current PM support, next-generation PM onboarding/go-live, and long-term platform buildout for larger-scale PMs.  
* The role is effectively a senior PMO / operating hub that “wrangles everything together,” understands PM needs, holds tech accountable, removes roadblocks, and can grow into a larger PMO function. 
* PMs should be “handheld all the way to go live,” and business-side execution should ensure they receive what was promised by onboarding / go-live. 
* The role sits in the middle of PMs, business, and tech, translating PM needs into clear work and identifying underserved areas and unclear success criteria. 
* The biggest leverage point is **happy, successful PMs**, especially by improving technology delivery and making PM needs visible and well-prioritized. 

---

## Product Vision

Create an internal execution platform that functions as the **business operating layer for BAM Systematic**.

It should:

* make PM needs explicit and queryable,
* convert vague asks into well-scoped work,
* tie work to business outcomes,
* expose dependencies and blockers,
* support recurring operating cadences,
* improve accountability across centralized technology,
* reduce execution chaos as the business scales,
* and provide a clean foundation for automation, reporting, and AI-assisted workflows.

In one sentence:

**The system should help BAM Systematic translate PM needs into clearly owned, measurable, and executable work that gets PMs onboarded and live faster while advancing the long-term platform roadmap.**

---

## Core Design Principles

1. **Business outcome first**

   * Every tracked item should connect back to a PM need, capability gap, or business objective.
   * The system should avoid “task tracking for its own sake.”

2. **Structure over free text**

   * Key artifacts (needs, milestones, risks, decisions, dependencies) should be first-class objects, not buried in comments.

3. **Execution clarity**

   * The system must answer: **who owns what, by when, and what does done mean?**

4. **Supports both short-term and long-term work**

   * Must handle urgent onboarding/go-live work *and* longer-horizon platform buildout.

5. **Operational, not ceremonial**

   * This is not a consultant-style reporting tool.
   * It should help operators move work forward, not just post updates. 

6. **Asana-native where possible**

   * Lean on Asana for project/task workflow.
   * Add a sidecar service only where Asana is weak (cross-project object modeling, advanced rollups, conversational access, custom intelligence).

7. **Agent-ready**

   * Data model and workflows should be designed so a future bot/agent can read, summarize, create, and route work safely.

---

## Target Users

### Primary users

* Business-side PMO / execution lead(s)
* Systematic business leadership
* PM coverage / onboarding leads

### Secondary users

* PMs / portfolio managers
* Systematic technology leadership
* Centralized technology partners
* Operations / broker / data / infra partners

### Future users

* Slack / Teams bot users
* AI copilots / internal agent tools
* Additional PMO staff as the function scales

---

## Scope of the First Build

### In scope

* Asana workspace / data model design
* standardized project templates
* required artifact types and field schema
* recurring operating cadences
* dashboards / rollups
* Python integration layer design
* chatbot / agent use cases
* safe create/update/query flows

### Out of scope for v1

* full autonomous decision-making
* deep analytics or forecasting
* replacing Asana
* replacing formal governance or executive decision-making
* direct integration into trading systems

---

## Core Artifact Model

The system should support the following artifact types.

### 1. Initiative

A top-level strategic effort that spans multiple projects.

Use this to represent one of the major business horizons:

* current PM support / optimization
* next-gen PM onboarding / go-live
* long-term platform buildout

**Fields**

* `initiative_id`
* `name`
* `horizon` (`short_term`, `medium_term`, `long_term`)
* `business_objective`
* `executive_sponsor`
* `priority`
* `status`
* `target_outcome`
* `linked_projects[]`

**Notes**

* In Asana: likely a **portfolio-level grouping** or top-level project/portfolio combo.

---

### 2. PM Coverage Record

A persistent record for each PM / team being supported.

This should be first-class because much of the role is organized around PM-specific needs and milestones. 

**Fields**

* `pm_id`
* `pm_name`
* `team_or_pod`
* `strategy_type`
* `region`
* `coverage_owner`
* `onboarding_stage`
* `go_live_target_date`
* `health_status`
* `top_open_needs[]`
* `top_blockers[]`
* `linked_projects[]`
* `last_touchpoint_date`

**Suggested onboarding stages**

* `pipeline`
* `pre_start`
* `requirements_discovery`
* `onboarding_in_progress`
* `uat`
* `go_live_ready`
* `live`
* `stabilization`
* `steady_state`

**Notes**

* Asana does not natively model this well; likely maintain as:

  * one dedicated “PM Coverage” project with one task per PM, or
  * a sidecar record mirrored into Asana.

---

### 3. PM Need

A normalized business request / need / ask from a PM or systematic leadership.

This is one of the most important objects in the whole system. The role explicitly needs to know “what’s in our list of PM needs” and how those translate to people and tech work. 

**Examples**

* historical market data for region X
* alt data feed onboarding
* DMA via broker Y
* security master coverage
* research compute / GPU access
* execution plumbing enhancement

**Fields**

* `pm_need_id`
* `pm_id`
* `title`
* `problem_statement`
* `business_rationale`
* `requested_by`
* `date_raised`
* `category` (`market_data`, `historical_data`, `alt_data`, `execution`, `broker`, `infra`, `research`, `ops`, `other`)
* `urgency`
* `business_impact`
* `desired_by_date`
* `status`
* `mapped_capability_id`
* `linked_project_ids[]`
* `resolution_path`
* `notes`

**Suggested statuses**

* `new`
* `triaged`
* `mapped_to_existing_capability`
* `needs_new_project`
* `in_progress`
* `blocked`
* `delivered`
* `deferred`
* `cancelled`

**Notes**

* Can be modeled in Asana as intake tasks in a dedicated **PM Needs** project.

---

### 4. Capability

A reusable platform capability that may support multiple PMs.

This avoids solving the same need repeatedly as bespoke one-offs. Nick explicitly describes pushing toward logical shared solutions instead of blindly giving each PM exactly what they ask for. 

**Examples**

* security master
* real-time market data
* historical market data
* alternative data onboarding
* DMA connectivity
* broker integration
* co-location
* research platform
* GPU access
* execution monitoring

**Fields**

* `capability_id`
* `name`
* `domain`
* `owner_team`
* `current_maturity`
* `description`
* `known_gaps[]`
* `dependent_pms[]`
* `linked_projects[]`
* `roadmap_status`

**Notes**

* Prefer sidecar or dedicated Asana project, depending complexity.

---

### 5. Project

A bounded execution effort that delivers a business outcome.

Every project should answer:

* what problem is being solved,
* for whom,
* by when,
* and what success looks like.

**Fields**

* `project_id`
* `name`
* `project_type` (`pm_onboarding`, `capability_build`, `remediation`, `expansion`, `investigation`)
* `business_objective`
* `primary_pm_ids[]`
* `owner`
* `status`
* `priority`
* `start_date`
* `target_date`
* `success_criteria`
* `linked_pm_needs[]`
* `linked_capabilities[]`
* `linked_milestones[]`
* `linked_risks[]`
* `linked_decisions[]`

**Notes**

* This should map directly to an **Asana project** in most cases.

---

### 6. Milestone

A named checkpoint with explicit gating criteria.

The transcripts clearly emphasize **onboarding** and **go-live** as critical milestones. 

**Examples**

* onboarding kickoff
* requirements confirmed
* data ready
* execution ready
* UAT complete
* go-live ready
* PM live
* stabilization complete

**Fields**

* `milestone_id`
* `project_id`
* `name`
* `target_date`
* `owner`
* `status`
* `gating_conditions`
* `acceptance_criteria`
* `confidence`

**Notes**

* In Asana: model as **milestone tasks** inside projects.

---

### 7. Deliverable / Action Item

A concrete owned work item.

This is the lowest-level tracked unit and should support the weekly “who will do what by when” execution cadence.

**Fields**

* `deliverable_id`
* `project_id`
* `title`
* `owner`
* `due_date`
* `status`
* `related_milestone_id`
* `blocked_by[]`
* `last_updated`
* `notes`

**Notes**

* In Asana: standard tasks/subtasks.

---

### 8. Dependency

A first-class representation of sequencing and coupling.

Dependencies should not be hidden in comments or tribal knowledge.

**Fields**

* `dependency_id`
* `predecessor_type`
* `predecessor_id`
* `successor_type`
* `successor_id`
* `dependency_type`
* `owner_of_predecessor`
* `risk_if_missed`
* `current_confidence`

**Notes**

* Use Asana task dependencies where possible.
* Cross-project dependencies may need sidecar support for better rollups.

---

### 9. Risk / Blocker / Issue

A trackable object for things threatening outcomes, dates, or confidence.

This is critical because the role explicitly needs to surface **underserved areas** and **unclear success criteria**. 

**Fields**

* `risk_id`
* `title`
* `type` (`risk`, `blocker`, `issue`)
* `severity`
* `impacted_pm_ids[]`
* `impacted_project_ids[]`
* `impacted_milestone_ids[]`
* `owner`
* `date_opened`
* `age_days`
* `mitigation_plan`
* `escalation_status`
* `resolution_date`

**Notes**

* Prefer dedicated section or dedicated “Risks & Blockers” project for visibility.

---

### 10. Decision

A durable record of meaningful business/technology tradeoffs.

This prevents repeated re-litigation and preserves rationale.

**Examples**

* choose broker A over broker B
* reuse existing capability instead of custom build
* phase work into v1/v2
* defer non-critical feature to hit go-live

**Fields**

* `decision_id`
* `title`
* `context`
* `options_considered`
* `chosen_path`
* `rationale`
* `approver(s)`
* `decision_date`
* `impacted_artifacts[]`

**Notes**

* Can be modeled in Asana as a dedicated project or as special tasks/comments, but a sidecar store is preferable if searchable history matters.

---

### 11. Status Update

A concise structured snapshot for stakeholders.

**Levels**

* project-level
* PM-level
* initiative-level

**Fields**

* `status_update_id`
* `scope_type`
* `scope_id`
* `overall_status`
* `what_changed_this_period`
* `next_key_milestones`
* `top_blockers`
* `decisions_needed`
* `confidence`
* `updated_by`
* `updated_at`

**Notes**

* In Asana: use project status updates where possible.

---

### 12. Stakeholder / Team Map

A lightweight map of who matters for delivery.

Useful for a highly cross-functional and geographically distributed org.

**Fields**

* `stakeholder_id`
* `name`
* `team`
* `function`
* `region`
* `relationship_owner`
* `role_in_delivery`
* `meeting_cadence`
* `linked_projects[]`

**Notes**

* Optional in v1; likely best in sidecar or lightweight reference project.

---

## Minimum Viable Schema for V1

If the team must keep v1 tight, the minimum required objects are:

* PM Coverage Record
* PM Need
* Project
* Milestone
* Deliverable
* Risk / Blocker
* Decision
* Status Update

Add later in v2:

* Capability
* Initiative
* Stakeholder Map
* richer dependency graph
* advanced automation / bot actions

---

## Common Workflows

### 1. New PM Onboarding Workflow

This should be the flagship workflow.

**Goal**
Get an incoming PM from pipeline/pre-start to live as smoothly and quickly as possible while ensuring promised capabilities are delivered. 

**Flow**

1. Create PM Coverage Record
2. Create Onboarding Project from template
3. Seed initial milestones
4. Capture PM Needs
5. Map each need to:

   * existing capability, or
   * new project / workstream
6. Create deliverables
7. Track dependencies and risks
8. Run weekly review until go-live
9. Run post-go-live stabilization
10. Transition to steady-state coverage

**Default onboarding milestones**

* kickoff
* requirements confirmed
* market data ready
* historical data ready
* alt data ready
* execution ready
* UAT complete
* go-live ready
* PM live
* stabilization complete

---

### 2. PM Need Intake and Routing Workflow

**Goal**
Convert a PM ask into a clear routed execution path.

**Flow**

1. Capture PM Need
2. Triage category / urgency / impact
3. Check for existing capability / existing in-flight solution
4. If existing solution applies:

   * link to capability/project
   * set expectation
5. If not:

   * create new project or backlog item
6. Define success criteria
7. Assign owners
8. Include in next operating review

**Key rule**
No PM ask should remain as vague free text. Every ask should end up:

* mapped,
* prioritized,
* owned,
* and visible.

---

### 3. Cross-Functional Delivery Workflow

**Goal**
Translate business-side needs into executable work across tech and partner teams.

**Flow**

1. Start from PM Need or Capability Gap
2. Create/identify linked Project
3. Define business objective and success criteria
4. Break into milestones
5. Break into deliverables
6. Assign owners across business + tech
7. Track dependencies
8. Review progress weekly
9. Escalate blockers
10. Close only after business-side acceptance

**Key rule**
Every tech effort should tie back to a clear business outcome. 

---

### 4. Weekly Operating Review Workflow

**Goal**
Run the execution system across all active work.

**Inputs**

* active projects
* overdue deliverables
* milestone slips
* open blockers
* PMs at risk
* decisions needed

**Outputs**

* reprioritized items
* escalations
* updated dates/owners
* refreshed status updates
* list of leadership talking points

**Key rule**
The system should generate the agenda automatically from the artifacts.

---

### 5. Escalation / Accountability Workflow

**Trigger conditions**

* milestone at risk
* repeated missed deliverables
* unclear owner
* unclear success criteria
* unexplained tech delay
* PM confidence dropping

**Flow**

1. Open or update Risk / Blocker
2. Link impacted PM/project/milestone
3. Assign escalation owner
4. Record decision needed
5. Surface in operating review / leadership cadence
6. Resolve / replan / re-scope

**Key rule**
Delays and ambiguity should become visible quickly instead of lingering in meetings. This directly addresses the problem that tech can “move the bullseye” if nobody pins down the target. 

---

### 6. Post-Go-Live Stabilization Workflow

**Goal**
Do not treat “live” as the end. Ensure early usage and support are actually working.

**Flow**

1. Mark PM live milestone complete
2. Start stabilization checklist
3. Capture early issues / misses
4. Create follow-up PM Needs
5. Separate support items from roadmap items
6. Close only after stabilization criteria met

---

### 7. Platform Capability Roadmap Workflow

**Goal**
Convert repeated PM needs into shared platform investments.

**Flow**

1. Aggregate PM Needs
2. Cluster repeated asks
3. Create/update Capability records
4. Prioritize based on business leverage
5. Create Initiative + linked Projects
6. Sequence milestones (foundation, v1, expansion)
7. Track which PMs are unblocked by each capability

---

## Core Operating Cadence / Meeting Use Cases

The system must support these recurring operating moments.

### 1. Project-Specific Working Session

For one concrete project.

**Purpose**
Drive execution forward.

**Cadence**
Usually weekly.

**Consumes**

* project
* milestones
* deliverables
* blockers
* dependencies
* decisions

**Produces**

* updated owners/dates
* new blockers
* updated milestone confidence
* new action items

---

### 2. PM Onboarding Meeting

A specialized project meeting for one incoming PM/team.

**Purpose**
Keep an onboarding / go-live track moving.

**Cadence**
Weekly until live, then lighter during stabilization.

**Consumes**

* PM Coverage Record
* onboarding project
* PM needs
* onboarding milestones
* blocker log

**Produces**

* updated onboarding stage
* next milestone commitments
* escalations
* new PM needs

---

### 3. Daily Standup

Only for hot or time-sensitive workstreams.

**Purpose**
Fast unblock loop.

**Cadence**
Daily, 10–15 minutes, only for urgent streams.

**Good use cases**

* imminent launch
* severe blocker
* cutover
* production incident
* compressed timeline

**Consumes**

* deliverables due in next 1–3 days
* active blockers
* overnight changes

**Produces**

* immediate unblock actions
* escalations
* same-day priorities

---

### 4. Weekly Operating Review

The core management cadence.

**Purpose**
Run the business-side execution system across all active work.

**Cadence**
Weekly.

**Consumes**

* all active projects
* overdue tasks
* milestone slips
* PMs at risk
* blockers
* decisions needed

**Produces**

* reprioritized work
* escalation list
* updated health/confidence
* summary for leadership

---

### 5. PM Touchpoint / Relationship Check-In

Separate from pure project mechanics.

**Purpose**
Ensure PMs feel supported, heard, and that their needs are being translated into visible work.

**Cadence**
Biweekly or monthly per PM.

**Consumes**

* PM record
* open needs
* status of prior asks
* current health

**Produces**

* new needs
* PM sentiment signal
* priority adjustments
* expectation alignment

This supports the explicit goal of “happy PMs” who feel seen and whose needs are matched to clear prioritized work. 

---

### 6. Business–Technology Coordination Meeting

The bridge into centralized tech.

**Purpose**
Translate business needs into tech priorities and maintain accountability.

**Cadence**
Weekly.

**Consumes**

* prioritized PM needs
* linked projects
* delayed milestones
* unclear success criteria
* tech dependencies

**Produces**

* priority confirmations
* ownership clarifications
* date updates
* escalations

This directly reflects the need for business-side coordination with centralized functions, especially technology. 

---

### 7. Monthly Roadmap / Vision Review

The “look up” meeting.

**Purpose**
Review whether execution is advancing the right longer-term platform.

**Cadence**
Monthly.

**Consumes**

* initiatives
* capability roadmap
* repeated PM need trends
* PM pipeline
* delivery bottlenecks
* resource constraints

**Produces**

* roadmap adjustments
* capability reprioritization
* re-scoping decisions
* requests for leadership support

This should align explicitly to the three business horizons:

* support/invest in current PMs,
* get incoming PMs live,
* build the long-term platform. 

---

### 8. Milestone Readiness Review

A focused gate check before major checkpoints.

**Examples**

* data ready
* execution ready
* go-live ready

**Purpose**
Validate readiness using explicit criteria, not optimism.

**Cadence**
Ad hoc, typically 1–2 weeks before a major milestone.

**Consumes**

* milestone
* acceptance criteria
* linked deliverables
* blockers
* risks

**Produces**

* go / no-go / conditional go
* gap list
* mitigation plan
* updated confidence

---

### 9. Risk / Blocker Escalation Review

A focused problem-solving session.

**Purpose**
Resolve stuck items and force clarity.

**Cadence**
Weekly or as part of operating review.

**Consumes**

* all open blockers
* aging issues
* milestone-impacting risks
* missing owners
* pending decisions

**Produces**

* escalation owner
* resolution path
* decision asks
* replanned dates if needed

---

### 10. Post-Go-Live Stabilization Review

Do not declare victory too early.

**Purpose**
Ensure the PM is actually functional and supported after launch.

**Cadence**
Weekly for 2–6 weeks post-go-live.

**Consumes**

* stabilization checklist
* early issues
* PM feedback
* follow-on asks

**Produces**

* support actions
* new backlog items
* satisfaction/health update
* closure decision

---

## Non-Meeting Use Cases the System Must Support

These should be queryable directly via UI and later via bot/agent.

### A. “What’s the status of PM X?”

Return:

* onboarding stage
* next milestone
* top blockers
* overall health
* top open needs
* last update

### B. “What is delaying go-live for PM Y?”

Return:

* blocked milestones
* unresolved dependencies
* open blockers
* owners
* age of blocker
* escalation state

### C. “What are the top PM needs across the business?”

Return:

* repeated asks
* category distribution
* unmet needs by PM
* clustered capability gaps
* oldest unresolved asks

### D. “Which projects are at risk this month?”

Return:

* slipped milestones
* overdue deliverables
* high severity blockers
* impacted PMs
* risk owners

### E. “Create a new PM onboarding project”

Should:

* create PM coverage record
* instantiate onboarding template
* create default milestones
* create intake checklist
* assign owners and dates

### F. “Prepare tomorrow’s weekly operating review”

Should:

* identify overdue items
* list milestone slips
* show PMs at risk
* list decisions needed
* propose an agenda

### G. “What decisions are pending right now?”

Should:

* list open decisions by urgency
* show impacted PMs/projects
* show requested approvers
* show oldest pending item

### H. “Which capabilities are creating the most drag?”

Should:

* cluster repeated PM needs by capability area
* show linked blockers and delayed projects
* rank by business impact

---

## Recommended Asana Mapping

Use Asana as the default system of record for execution.

### Asana-native objects

**Asana Project**

* maps to: `Project`
* use for onboarding projects, capability build projects, remediation projects

**Asana Task**

* maps to: `Deliverable`, `PM Need`, or record row in lightweight tracking projects

**Asana Milestone**

* maps to: `Milestone`

**Asana Section**

* use to segment work:

  * intake
  * active
  * blocked
  * done
  * by workstream / phase / capability

**Asana Custom Fields**
Use aggressively. Recommended fields:

* project type
* PM
* urgency
* business impact
* owner group
* health
* milestone confidence
* risk severity
* target date
* linked capability
* region
* decision status

**Asana Dependencies**

* use for task-level sequencing
* supplement with sidecar for cross-project visibility if needed

**Asana Portfolios**

* use for initiatives / project rollups
* likely best home for short/medium/long-term horizons

**Asana Status Updates**

* use for structured project status snapshots

**Asana Templates**

* required for:

  * PM onboarding
  * capability build
  * escalation
  * stabilization
  * recurring meeting agendas/checklists

**Asana Forms**

* optional but recommended for PM need intake

---

## Sidecar Service Responsibilities

A lightweight Python service should exist outside Asana for capabilities Asana handles poorly.

### Use the sidecar for

* cross-project object linking
* richer PM Coverage Records
* capability clustering / rollups
* decision registry
* cross-project risk heatmaps
* bot-facing query layer
* sync logic for standard templates and metadata
* audit-safe create/update workflows
* optional summarization / notification logic

### Avoid putting in sidecar (unless necessary)

* core task execution
* everyday manual project management
* basic assignments and due dates
* project comments / routine collaboration

### Suggested sidecar architecture

* Python app (FastAPI recommended)
* Asana REST API integration
* webhook receiver
* small relational DB (Postgres or SQLite to start)
* job runner / scheduler
* Slack/Teams bot adapter
* optional LLM-facing tool layer

---

## Automation / Integration Requirements

### Technical requirements

The system should support:

* Asana API read/write
* webhook/event-driven sync
* template-based object creation
* scheduled digest generation
* chat-triggered create/read/update flows
* permission-aware actions
* idempotent automation patterns
* safe retries and logging

### Initial automation ideas

1. **Daily digest**

   * overdue tasks
   * milestones due in 7 days
   * blocked items
   * PMs at risk

2. **Weekly review prep**

   * auto-generate agenda
   * list slips, risks, decisions

3. **Milestone watch**

   * alert when major milestones lack acceptance criteria
   * alert when milestone is near but linked tasks incomplete

4. **PM health watch**

   * alert when a PM has aging open needs or repeated blockers

5. **Decision aging**

   * alert when pending decisions exceed threshold

6. **Template enforcement**

   * ensure new onboarding projects get all required milestones/fields

---

## Chatbot / Agent Layer

A future Slack or Teams bot should sit on top of the sidecar + Asana.

### Design goal

Allow users to query and create structured work **without bypassing governance**.

### Bot principles

* never create free-form chaos
* always route through templates
* always require core metadata
* always link new work to PM / project / capability / initiative where possible
* summarize before writing if action is high-impact
* preserve audit log of created/modified records

### Initial bot commands / intents

**Read/query**

* “What’s the status of PM X?”
* “What’s blocking Project Y?”
* “What’s at risk this week?”
* “What decisions are pending?”
* “Show open PM needs for region Z.”
* “What capability gaps are coming up most often?”

**Create**

* “Create a new PM onboarding project for [PM].”
* “Log a new PM need for [PM].”
* “Open a blocker on [project].”
* “Create a milestone readiness review task.”
* “Create this month’s roadmap review agenda.”

**Update**

* “Mark this blocker escalated.”
* “Move PM X to go-live-ready.”
* “Update health to yellow for Project Y.”
* “Add a decision record for broker choice.”

### Suggested safe flow for create actions

1. Bot collects required inputs
2. Bot validates template and destination
3. Bot creates objects in Asana (+ sidecar if needed)
4. Bot returns summary + links
5. Bot logs action for traceability

---

## Data / Reporting Requirements

The system should provide at least the following views.

### PM View

For each PM:

* stage
* target go-live
* health
* top needs
* top blockers
* linked projects
* recent updates

### Project View

For each project:

* business objective
* status
* next milestones
* overdue deliverables
* blockers
* decisions needed
* dependencies

### Operating Review View

Across all active work:

* overdue deliverables
* milestone slips
* PMs at risk
* blockers by severity
* upcoming milestone calendar
* decisions awaiting action

### Roadmap View

Across strategic efforts:

* initiatives by horizon
* top capability gaps
* repeated PM need clusters
* current bottlenecks
* projects by stage and health

### Executive Summary View

For leadership:

* PMs in onboarding / live / stabilization
* go-live timeline
* most important blockers
* capabilities most constraining growth
* major upcoming decisions

---

## Success Criteria for the Build

The system is successful if it enables the business-side execution lead to do the following reliably:

1. See all active PMs and their current stage
2. Maintain a clean list of PM needs
3. Map PM needs to existing capabilities or new projects
4. Track onboarding and go-live milestones clearly
5. Surface blockers and unclear ownership quickly
6. Prepare for weekly and monthly operating cadences with minimal manual prep
7. Hold cross-functional partners accountable with visible dates, dependencies, and criteria
8. Answer status questions quickly and consistently
9. Create new standardized projects rapidly
10. Scale the operating model as more PMs and more PMO staff are added

---

## Non-Goals / Failure Modes to Avoid

### Do not build

* a generic task manager with no business model
* a giant custom system that replaces Asana unnecessarily
* an LLM agent that can create unstructured work freely
* a dashboard-only system with no operational writeback
* a “status theater” tool that increases meetings but not clarity

### Watch for these failure modes

* too much free text
* unclear ownership
* duplicate data between Asana and sidecar with no source-of-truth rules
* overcomplicated schema too early
* poor template hygiene
* bot actions that bypass required metadata
* failure to tie tech work to business outcomes

---

## Recommended Phased Delivery

### Phase 1: Core Operating System

Build the minimum viable foundation.

**Deliver**

* Asana workspace structure
* project templates
* required custom fields
* PM Needs intake project
* PM Coverage mechanism
* onboarding template
* blocker/risk tracking pattern
* operating review dashboard
* status update conventions

**Outcome**
A disciplined manual operating system can run without any advanced automation.

---

### Phase 2: Sidecar + Automation

Add structure and leverage.

**Deliver**

* Python sidecar service
* Asana sync layer
* richer PM Coverage model
* decision registry
* recurring digests
* review agenda generation
* milestone watch alerts
* basic API endpoints for querying

**Outcome**
Less manual overhead; better cross-project intelligence.

---

### Phase 3: Chat / Agent Interface

Add conversational access.

**Deliver**

* Slack or Teams bot
* read/query commands
* safe template-based create flows
* guarded update flows
* audit logs

**Outcome**
Fast access and creation without losing structure.

---

### Phase 4: Intelligence / Optimization

Add more advanced insights once the data model is stable.

**Potential future features**

* PM happiness / risk heuristics
* capability gap ranking
* launch-readiness scoring
* blocker aging prioritization
* recurring pattern detection across PMs
* recommended prioritization queues

---

## Source of Truth Rules

To avoid confusion, the team should adopt explicit source-of-truth boundaries.

### Asana is source of truth for

* active project structure
* tasks and milestones
* day-to-day ownership and due dates
* project status updates
* team collaboration around execution

### Sidecar is source of truth for

* cross-project relational logic
* richer PM Coverage records
* capability rollups
* decision registry
* bot query layer
* advanced derived views and automation state

### Sync rules

* every sidecar record that mirrors Asana should store the relevant Asana GID
* writes should be idempotent
* deletion/archival behavior should be explicit
* avoid dual-write ambiguity whenever possible

---

## Open Implementation Questions the Team Should Resolve

The team should make and document explicit decisions on the following:

1. Will PM Coverage live primarily in Asana or in the sidecar?
2. How should cross-project dependencies be represented when Asana native dependencies are insufficient?
3. Will Decisions be first-class in Asana, sidecar-only, or hybrid?
4. What auth model will be used for bot actions?
5. Which chat platform is first: Slack or Teams?
6. What level of approval is required for project creation vs task creation?
7. What are the mandatory fields for PM Need intake?
8. What thresholds should trigger risk/escalation alerts?
9. What is the archival model for completed PM onboarding projects?
10. What naming conventions will be enforced for projects, milestones, and PM records?

If forced to choose quickly, bias toward:

* simpler schema,
* stronger templates,
* explicit source-of-truth boundaries,
* and fewer but more reliable automations.

---

## Recommended Naming Conventions

### Projects

`[Type] - [PM or Capability] - [Short Outcome]`

Examples:

* `Onboarding - PM Jane Doe - US Equities Launch`
* `Capability - Security Master - Phase 1`
* `Remediation - Historical Data - Coverage Gaps`

### Milestones

`[Project] - [Checkpoint]`

Examples:

* `PM Jane Doe - Data Ready`
* `PM Jane Doe - Go Live Ready`

### PM Needs

`[PM] - [Need Category] - [Short Need]`

Examples:

* `Jane Doe - Execution - DMA via Goldman`
* `John Smith - Alt Data - Vendor X Access`

### Risks / Blockers

`[Scope] - [Short Problem]`

Examples:

* `PM Jane Doe - Historical Data Feed Delayed`
* `Security Master - Ownership Unclear`

---

## Final Product Summary

Build a **BAM Systematic Execution Operating System** that combines:

* **Asana for structured execution**
* **a Python sidecar for cross-project intelligence and automation**
* **a future chat/agent layer for safe conversational access**

The core job-to-be-done is:

* keep a clear list of PM needs,
* translate them into visible, owned work,
* support onboarding and go-live,
* surface blockers and unclear criteria early,
* coordinate with centralized technology,
* and help the business scale from ad hoc execution to a repeatable PMO operating model.

This should feel like a **business-side execution cockpit**, not just a ticketing tool.

If the team is unsure how to prioritize, the correct bias is:

1. make PM needs visible,
2. make onboarding/go-live milestones explicit,
3. make blockers and decisions easy to surface,
4. make weekly/monthly operating cadences easy to run,
5. then add automation and conversational access on top.
