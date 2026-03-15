# AGENTS.md — Kinawa CC v2

Local operating contract for the reimagined Kinawa Command Center.

Reference standard: `docs/BTG_AGENTS_STANDARD.md`

---

## Project Overview
- **Name:** Kinawa Command Center v2
- **Purpose:** Child care operations hub — staff scheduling, licensing compliance, training certificates, GFS reconciliation
- **Stack:** Flask, SQLAlchemy/Alembic, PostgreSQL, Jinja2 + HTMX, systemd/nginx
- **Project category:** Category A (application code)

## Workflow Mode
- **Category A:** author locally, hand off through GitHub, run on VPS
- VPS is **runtime truth**, not routine authoring truth

## Canonical Locations / Paths
- **Canonical local authoring repo:** `~/.openclaw/workspace/projects/kinawa-cc-v2/`
- **GitHub repo:** `behindthegarage/kinawa-cc-v2` (to be created)
- **VPS runtime path:** `/home/openclaw/kinawa-cc-v2/`
- **Canonical runtime host:** VPS (162.212.153.134)
- **Expected hostname for host-bound edits:** `p5gHxcyh7WDx`
- **Public domain:** `https://clubkinawa.net` (existing, will migrate)
- **Rule:** If task is host-bound and `hostname` is not `p5gHxcyh7WDx`, stop and SSH to VPS first

## Setup Commands (Local)
- **Enter local repo:** `cd ~/.openclaw/workspace/projects/kinawa-cc-v2/`
- **Activate environment:** `source venv/bin/activate`
- **Install dependencies:** `pip install -r requirements.txt`
- **Initialize local config:** `cp .env.example .env` (edit as needed)
- **Start local/dev server:** `flask run` or `python run.py`
- **One useful local health check:** `curl http://localhost:5000/health`

## Dev Commands
- **Install:** `pip install -r requirements.txt`
- **Run locally:** `flask run --debug`
- **Tests:** `pytest` (to be added)
- **Lint:** `flake8 app/` (to be added)
- **Build:** N/A (Python app)
- **Manual verification:** Login at `/`, verify staff schedule loads, verify licensing checklist displays

## Deployment
- **Deploy method:** GitHub Actions or controlled VPS pull
- **Deploy rail:** local commit → GitHub push → VPS pull → service restart
- **Deploy steps:**
  1. `git add . && git commit -m "message" && git push origin main`
  2. SSH to VPS: `ssh openclaw@162.212.153.134`
  3. `cd /home/openclaw/kinawa-cc-v2 && git pull origin main`
  4. `sudo systemctl restart kinawa-cc-v2`
- **Restart service:** `sudo systemctl restart kinawa-cc-v2`
- **Reload proxy/nginx:** `sudo systemctl reload nginx`
- **Post-deploy verification:** `curl https://clubkinawa.net/health`
- **Emergency hotfix rule:** If edited on VPS, sync back to local repo immediately and push

## Service Map
- **systemd service:** `kinawa-cc-v2.service`
- **nginx config:** `/etc/nginx/sites-available/clubkinawa.net`
- **App port:** `127.0.0.1:5000`
- **Health URL:** `https://clubkinawa.net/health`
- **Runtime data/storage:** PostgreSQL `kinawa_cc_v2` database
- **Production source of truth:** VPS PostgreSQL + uploaded certificate files

## Environment / Secrets Handling
- **Env file location:** `.env` (local), `/home/openclaw/kinawa-cc-v2/.env` (VPS)
- **Required secrets:** `SECRET_KEY`, `DATABASE_URL`, `BASIC_AUTH_PASSWORD`
- **Secret source:** `.env` file (never commit)
- **Never commit:** `.env`, `*.pem`, `__pycache__/`, `.venv/`

## Version / Release Discipline
- **Canonical version location:** `app/__init__.py` (`__version__`)
- **Release rule:** Bump version only on explicit release intent
- **Tagging rule:** Tag releases as `v1.0.0`, `v1.1.0`, etc.
- **Post-deploy check:** Verify `/health` returns expected version

## Verification Checklist
After changes:
- [ ] `hostname` confirmed (if VPS-bound)
- [ ] `git status` clean
- [ ] Local dev server starts without errors
- [ ] Service restart successful
- [ ] Logs clean (`journalctl -u kinawa-cc-v2 --since "1 min ago"`)
- [ ] Health endpoint responds correctly
- [ ] Manual verification path completed
- [ ] Version matches expectation

## Logs / Debugging
- **Service logs:** `sudo journalctl -u kinawa-cc-v2 -f`
- **App logs:** `tail -f /home/openclaw/kinawa-cc-v2/logs/app.log`
- **Common failure modes:** 
  - DB connection errors (check `DATABASE_URL`)
  - Missing env vars (check `.env`)
  - Permission errors on uploads directory
- **Useful diagnostics:** `flask db current`, `flask db migrate`

## Known Traps
- Local repo ≠ VPS runtime (Category A discipline required)
- PostgreSQL migrations must be run manually on VPS: `flask db upgrade`
- Upload directory must be writable by `openclaw` user
- CC v1 data (`data.json`) is NOT compatible with v2 PostgreSQL schema
- GFS reconciliation module requires matching catalog DB (to be migrated)

## Docs Sync Rule
Update these when behavior changes:
- `README.md` — User-facing docs
- `DESIGN.md` — Architecture decisions
- `AGENTS.md` — This file (ops workflow)
- `.env.example` — Config template

## Guardrails
- Author locally by default; do not routine-edit on VPS
- Verify `hostname` before VPS-bound work
- One change at a time, then test
- Back up risky config before changing
- Trust prod evidence over local assumptions
- Minimal actionable checks over aspirational tests

## Rollback
- **Git rollback:** `git revert HEAD` or `git reset --hard <commit>`
- **Config restore:** Copy from `.env.backup` or version control
- **Service restart:** `sudo systemctl restart kinawa-cc-v2`
- **Last known good:** Document in deployment notes

## External Dependencies
- **Training Certificate Manager:** To be integrated (separate service at `pd.okemoskidsclub.com`)
- **GFS Reconciliation:** Port working code from CC v1
- **Google Workspace (optional):** For calendar sync (gws CLI)
