# Kinawa Command Center v2

Reimagined child care operations hub for Club Kinawa.

## What This Is

A focused tool for managing child care program operations:
- **Staff Scheduling** — Weekly view, shift assignment, printable postings
- **Licensing Compliance** — Checklists, training status, CCL-4591 generation
- **GFS Reconciliation** — Invoice upload, auto-reconciliation, email reports

## Quick Start

```bash
# Setup
cd ~/.openclaw/workspace/projects/kinawa-cc-v2/
cp .env.example .env
# Edit .env with your settings

# Install dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Run locally
flask run
```

## Documentation

- **Project overview:** `projects/kinawa-cc-v2.md`
- **Design document:** `DESIGN.md`
- **Operations guide:** `AGENTS.md`

## Architecture

- **Backend:** Flask + SQLAlchemy + PostgreSQL
- **Frontend:** Jinja2 + HTMX
- **Deployment:** systemd + nginx on VPS

## Status

🔧 **Active development** — Ground-up rebuild in progress.

See `DESIGN.md` for detailed architecture and `projects/kinawa-cc-v2.md` for project status.
