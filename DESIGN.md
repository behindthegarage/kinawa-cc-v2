# Kinawa CC v2 — Design Document

> Software Design Description for the reimagined Kinawa Command Center

**Document Status:** Draft  
**Last Updated:** 2026-03-15  
**Related Project Doc:** `projects/kinawa-cc-v2.md`  
**Project Category:** Category A (application code)  
**Canonical Local Authoring Repo:** `~/.openclaw/workspace/projects/kinawa-cc-v2/`  
**GitHub Repo:** `behindthegarage/kinawa-cc-v2` (to be created)  
**VPS Runtime Path:** `/home/openclaw/kinawa-cc-v2/`  
**Owner / Stakeholders:** Adam (primary user), Hari (builder)

---

## 1. Executive Summary

### What are we building?
A focused operations tool for child care program management: staff scheduling, licensing compliance tracking, and GFS invoice reconciliation.

### Why does it exist?
CC v1 accumulated technical debt and UX friction. It tried to do too much. CC v2 is deliberately narrow: 3 features, done well, integrated where they matter.

### Why now?
- Licensing visit approaching — need reliable tracking
- Staff scheduling is manual — needs tool support
- GFS reconciliation works but is trapped in v1's mess

### Success signal
Adam uses it weekly without prompting because it reduces friction.

---

## 2. Goals / Non-Goals

### Goals
- G1: Staff schedule — weekly view, shift assignment, printable posting
- G2: Licensing compliance — canonical checklists, training status visibility
- G3: GFS reconciliation — port working code, fix kinks
- G4: Training Certificate Manager integration — display status, generate CCL-4591

### Non-Goals
- NOT a general calendar (Google Calendar exists)
- NOT a full HR system (payroll, benefits, etc.)
- NOT a parent portal
- NOT real-time chat/messaging
- NOT mobile app (mobile-web responsive only)

### Design principles
- Start simple, add only when proven necessary
- Category A: local authoring → GitHub → VPS runtime
- Optimize for "glance and act" — minimal clicks to complete tasks
- Print-friendly outputs matter (postings, reports)

---

## 3. Requirements

### Functional Requirements
- FR1: Weekly staff schedule view (Mon-Fri, Before/After care shifts)
- FR2: Shift assignment interface (drag/select, save, print)
- FR3: Licensing checklist with completion tracking
- FR4: Training certificate status per staff (from TCM)
- FR5: CCL-4591 form generation
- FR6: GFS invoice upload (CSV + PDF)
- FR7: GFS auto-reconciliation with approval workflow
- FR8: Email reconciliation reports

### Non-Functional Requirements
- **Performance:** Page load < 2s, schedule view < 1s
- **Reliability:** 99% uptime (VPS + systemd)
- **Security:** Basic auth sufficient (internal tool)
- **Privacy:** Staff data encrypted at rest (PostgreSQL)
- **Operability:** Clear logs, health endpoint, simple restart
- **Maintainability:** Alembic migrations, clear module boundaries
- **Cost:** Minimal (existing VPS, no new services)

### Acceptance Criteria
- [ ] Schedule view loads weekly staff assignments
- [ ] Shift assignment saves and persists
- [ ] Print view generates clean posting format
- [ ] Licensing checklist shows completion status
- [ ] Training status queries TCM and displays correctly
- [ ] GFS upload → reconcile → approve → email flow works
- [ ] Mobile responsive (usable on phone)

---

## 4. Constraints / Assumptions

### Constraints
- Must use existing VPS (162.212.153.134)
- Must integrate with existing TCM (pd.okemoskidsclub.com)
- Must port GFS logic from v1 (don't rewrite working code)
- No dedicated mobile app (web only)
- No real-time updates (page refresh acceptable)

### Assumptions
- TCM will expose API for training status queries
- Staff count stable (~9 people)
- Licensing requirements stable (annual cycle)
- GFS invoice format unchanged

### Unknowns
- TCM API design (may need to add endpoints)
- GFS catalog DB migration complexity
- User acceptance of HTMX vs full SPA

---

## 5. Resource Plan

| Phase | Tokens | Attention | Parallel | Description |
|-------|--------|-----------|----------|-------------|
| Design | ~15K | medium | inline | This doc, schema, API design |
| Scaffold | ~25K | low | 1 agent | Flask app, DB, auth, base templates |
| Staff Schedule | ~30K | medium | 1 agent | Weekly view, assignment, print |
| Licensing | ~35K | high | 1-2 agents | Checklists, TCM integration, CCL-4591 |
| GFS Port | ~15K | medium | 1 agent | Port working code, fix kinks |
| Deploy | ~10K | medium | inline | VPS setup, nginx, migrate, verify |

**Total:** ~130K tokens, medium attention, sequential with focused sub-agents

---

## 6. System Context

### Users / actors
- **Primary:** Adam (director) — schedules staff, tracks licensing, reconciles GFS
- **Secondary:** Staff members (view-only schedule, training status)

### External dependencies
- **Training Certificate Manager (TCM):** Source of truth for training records
- **PostgreSQL:** Primary database
- **nginx:** Reverse proxy, SSL termination
- **systemd:** Process management
- **Google Workspace (optional):** Calendar sync (future)

### Context Diagram
```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Adam (User)   │────>│  CC v2 (Web) │────>│  PostgreSQL     │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               │ queries
                               ▼
                        ┌──────────────┐
                        │     TCM      │
                        │ (pd.okemos-  │
                        │ kidsclub.com)│
                        └──────────────┘
```

---

## 7. Architecture Overview

### Proposed Architecture
Flask monolith with clear module separation:
- `app/models/` — SQLAlchemy models
- `app/routes/` — Blueprint-based route modules
- `app/services/` — Business logic
- `app/templates/` — Jinja2 templates
- `app/static/` — CSS, minimal JS (HTMX)

### Major Components
| Component | Responsibility | Notes |
|-----------|----------------|-------|
| Staff Schedule | Weekly view, assignment, print | HTMX for interactivity |
| Licensing | Checklists, completion tracking | Read-only from TCM |
| GFS | Upload, parse, reconcile, email | Ported from v1 |
| Auth | Basic auth, session management | Simple, sufficient |
| Admin | Staff management, system config | Minimal viable |

### Architectural Decisions
| Decision | Choice | Rationale | Tradeoff |
|----------|--------|-----------|----------|
| Stack | Flask + SQLAlchemy | Familiar, proven, matches TCM | Less "modern" than FastAPI |
| Frontend | Jinja2 + HTMX | Simpler than React, server-rendered | Less interactive than SPA |
| Database | PostgreSQL | Production-grade, matches TCM | More complex than SQLite |
| TCM Integration | API queries | TCM remains source of truth | Requires TCM API development |
| GFS | Port, don't rewrite | Working code, reduce risk | Carries some v1 debt |

### Alternatives Considered
| Alternative | Why Not Chosen |
|-------------|----------------|
| FastAPI | Flask is sufficient, team familiarity |
| React frontend | Overkill for this use case |
| SQLite | Concurrent access needs, TCM uses PostgreSQL |
| Full TCM integration (shared DB) | Boundaries matter, TCM is separate service |

---

## 8. Component Design

### Component: Staff Schedule
**Purpose:** Display weekly schedule and allow shift assignments

**Inputs:**
- Week selection (date)
- Staff assignments (POST data)

**Outputs:**
- Weekly grid view (HTML)
- Print-friendly posting (HTML)
- Saved assignments (DB)

**Dependencies:**
- Staff model
- ScheduleAssignment model

**Failure modes:**
- Double-booking staff (prevent in UI)
- Unassigned shifts (highlight in view)

**Operational notes:**
- Mon-Fri only (school days)
- Before Care (6:45-9am), After Care (2:30-6pm)

### Component: Licensing
**Purpose:** Track compliance checklist, display training status

**Inputs:**
- Checklist item completions
- TCM training status queries

**Outputs:**
- Compliance dashboard
- CCL-4591 form (PDF/HTML)

**Dependencies:**
- ChecklistItem model
- TCM API

**Failure modes:**
- TCM unavailable (graceful degradation, show cached status)
- Missing training records (flag for manual review)

### Component: GFS Reconciliation
**Purpose:** Upload, parse, reconcile GFS invoices

**Inputs:**
- CSV file (invoice data)
- PDF file (original invoice)

**Outputs:**
- Reconciliation report (PDF)
- Email to stakeholders

**Dependencies:**
- GFS catalog DB
- Email service (SMTP)

**Failure modes:**
- Parse errors (show in UI, allow manual fix)
- Email failure (queue for retry)

---

## 9. Data Design

### Core Entities
| Entity | Description | Source of truth |
|--------|-------------|-----------------|
| Staff | Child care staff members | CC v2 DB |
| ScheduleAssignment | Staff assigned to shift on date | CC v2 DB |
| ChecklistItem | Licensing requirement checklist | CC v2 DB |
| ChecklistCompletion | Staff completion of checklist item | CC v2 DB |
| GFSReconciliation | Invoice reconciliation record | CC v2 DB |
| TrainingRecord | Approved training (read from TCM) | TCM |

### Schema Notes
- Staff: id, full_name, hire_date, active
- ScheduleAssignment: id, staff_id, date, shift_type (before/after)
- ChecklistItem: id, category, name, description, required_for
- ChecklistCompletion: id, staff_id, item_id, completed_at, evidence_url
- GFSReconciliation: id, invoice_number, created_at, status, pdf_path

### Data Lifecycle
- Staff: Create on hire, soft-delete on departure
- ScheduleAssignment: Create weekly, update as needed, archive after 1 year
- ChecklistCompletion: Create on completion, immutable
- GFSReconciliation: Create on upload, finalize on approval

### Data Quality
- Validate no double-booking in schedule
- Require evidence URL for checklist completions
- SHA256 verify uploaded PDFs

---

## 10. Interface / API Design

### External Interfaces
| Interface | Method | Purpose |
|-----------|--------|---------|
| TCM API | GET /api/staff/{id}/training | Query training status |
| TCM API | GET /api/staff/{id}/ccl-4591 | Generate CCL-4591 |
| Email | SMTP | Send reconciliation reports |

### Internal Interfaces
- `/schedule/` — Weekly schedule view
- `/schedule/assign` — POST shift assignment
- `/schedule/print` — Print-friendly view
- `/licensing/` — Compliance dashboard
- `/licensing/checklist/{staff_id}` — Staff checklist
- `/gfs/` — Upload interface
- `/gfs/reconcile` — POST reconcile action
- `/health` — Health check

### Human Interface
- Schedule: Click cell → select staff → save → print
- Licensing: View checklist → click complete → upload evidence
- GFS: Upload CSV → upload PDF → review → approve → email

---

## 11. State, Flows, and Behavior

### Primary Flows

**Flow 1: Assign Staff to Shift**
1. Navigate to schedule view
2. Select week
3. Click shift cell
4. Select staff from dropdown
5. Save (HTMX POST)
6. Cell updates in place

**Flow 2: Complete Licensing Item**
1. Navigate to licensing dashboard
2. View staff checklist
3. Click "complete" on item
4. Upload evidence (optional)
5. Save
6. Status updates, progress bar advances

**Flow 3: Reconcile GFS Invoice**
1. Navigate to GFS
2. Upload CSV
3. Upload PDF
4. System parses and reconciles
5. Review results
6. Approve or adjust
7. Email report

### Error Flows
- Parse error → show in UI, allow manual entry
- TCM unavailable → show cached data, warning banner
- Save conflict → retry with fresh data

---

## 12. Security, Privacy, and Reliability

### Security
- Basic auth for all routes
- CSRF protection on forms
- File upload size limits
- Path traversal prevention on uploads

### Privacy
- Staff data encrypted at rest (PostgreSQL)
- No PII in logs
- Access logs retained 30 days

### Reliability
- systemd restart on failure
- Health endpoint for monitoring
- Database backups (daily)

---

## 13. Performance and Operational Design

### Performance Targets
- Page load: < 2 seconds
- Schedule query: < 100ms
- GFS reconcile: < 10 seconds (async if needed)

### Deployment Model
- Category A: local authoring → GitHub → VPS
- VPS: systemd service + nginx reverse proxy
- Port: 127.0.0.1:5000
- Domain: clubkinawa.net

### Observability
- Logs: systemd journal + app log file
- Health: `/health` endpoint (DB + basic check)
- Error tracking: log aggregation

### Rollback
- Code: `git revert` + redeploy
- DB: Daily backups, Alembic downgrades
- Config: `.env` version controlled (without secrets)

---

## 14. Testing and Validation

### Automated Checks
- Unit tests: models, services (pytest)
- Integration tests: API endpoints (pytest + Flask test client)
- Lint: flake8, black

### Manual Verification
1. Login → view schedule → assign shift → print
2. View licensing → complete item → verify progress
3. Upload GFS → reconcile → approve → receive email

### Definition of Done
- [ ] All acceptance criteria met
- [ ] Manual verification paths completed
- [ ] Deployed to VPS
- [ ] Adam confirms usability

---

## 15. Risks and Open Questions

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| TCM API delay | Medium | Build with mock data first, integrate later |
| GFS migration complexity | Medium | Test with real invoices in staging |
| User adoption | High | Keep v1 running parallel, iterate based on feedback |

### Open Questions
- Q1: Should v1 stay running during transition? (Recommendation: yes, 2-week overlap)
- Q2: Who else needs access? (Currently just Adam)

---

## 16. Decision Log

| Date | Decision | Reason | Revisit if |
|------|----------|--------|------------|
| 2026-03-15 | HTMX over React | Simpler, sufficient interactivity | UX proves insufficient |
| 2026-03-15 | PostgreSQL over SQLite | Production needs, TCM compatibility | Complexity too high |
| 2026-03-15 | Port GFS, don't rewrite | Working code, reduce risk | GFS logic fundamentally broken |

---

## 17. Appendix

### Migration Notes
- Staff list: Manual entry (9 people, one-time)
- GFS catalog: Export from v1, import to v2
- Training status: Query TCM (no migration needed)

### Print Format (Staff Schedule)
```
                    MONDAY      TUESDAY     WEDNESDAY   THURSDAY    FRIDAY
BEFORE CARE
  6:45-9:00am       [Name]      [Name]      [Name]      [Name]      [Name]

AFTER CARE
  2:30-6:00pm       [Name]      [Name]      [Name]      [Name]      [Name]
```

---

*End of Design Document*
