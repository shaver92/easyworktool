# Family Expense Tracker — Implementation Plan

<!-- /autoplan restore point: /Users/shaver/.gstack/projects/skyshenzhen-easyworktool/main-autoplan-restore-20260518-180853.md -->

Generated from [design doc](shaver-main-design-20260518-172239.md) on 2026-05-18.
Branch: main | Target: MVP (P0 items from design doc) | Status: **APPROVED** (autoplan review complete)

## Overview

Two-process system: FastAPI (Feishu Bot) for expense entry, Streamlit for analytics dashboard. SQLite WAL as shared data store. Target: deployable MVP in ~7 hours of dev time.

## Architecture

```
family-expense-tracker/
├── bot/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, Feishu event subscription
│   ├── parser.py            # Regex message parser
│   └── feishu_client.py     # Feishu API helpers (send msg, verify signature)
├── shared/
│   ├── __init__.py
│   ├── config.py            # Shared config: .env + TOML
│   ├── database.py          # SQLite Repository (port from feishu-streamlit-verify)
│   └── schema.sql           # DDL for users, categories, expenses, budgets
├── web/
│   ├── __init__.py
│   ├── app.py               # Streamlit entry point
│   ├── auth.py              # Feishu OAuth + Web PIN login
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── dashboard.py     # Weekly/monthly/yearly charts
│   │   ├── expense_form.py  # Web fallback entry form
│   │   ├── budget.py        # Budget settings + alerts
│   │   └── categories.py    # Custom category management
│   └── charts.py            # ECharts/Pandas chart helpers
├── tests/
│   ├── __init__.py
│   ├── test_parser.py       # Unit: regex parsing
│   ├── test_database.py     # Unit: CRUD, WAL behavior
│   ├── test_auth.py         # Unit: PIN validation, session
│   └── test_api.py          # Integration: bot endpoints
├── requirements.txt
├── .env.example
└── config.toml
```

### Component dependency graph

```
┌──────────────────────┐     ┌──────────────────────┐
│   Feishu Platform    │     │   Browser (family)   │
│   (event subscription)│     │   :8501              │
└────────┬─────────────┘     └──────────┬───────────┘
         │ POST /webhook                │ HTTP
         ▼                              ▼
┌─────────────────────┐    ┌──────────────────────────┐
│  bot/main.py        │    │  web/app.py (Streamlit)   │
│  FastAPI :8000      │    │  :8501                    │
│                     │    │                           │
│  parser.py ─────────┤    │  auth.py ──► Feishu OAuth │
│  feishu_client.py   │    │  pages/dashboard.py       │
└──────────┬──────────┘    │  pages/expense_form.py    │
           │               │  pages/budget.py          │
           │               │  charts.py (echarts)      │
           ▼               └────────────┬──────────────┘
┌──────────────────────────────────────────────────────┐
│              shared/database.py (Repository)          │
│              SQLite WAL — single file                 │
│              data/family_expenses.db                  │
└──────────────────────────────────────────────────────┘
```

Both processes share one SQLite file via WAL mode. No lock contention at family scale (<100 writes/day).

## Data Model (from design doc)

4 tables: `users`, `categories`, `expenses`, `budgets`. Full DDL in `shared/schema.sql`.

Key decisions:
- `amount` stored as positive for expense, negative for refund. `type` column distinguishes.
- `source` column tracks entry origin (feishu_bot | web)
- Privacy enforced at query layer: personal detail only for self + admin; family aggregate visible to all
- WAL mode enabled at connection init

## Implementation Steps

### P0 — MVP (~7h)

| # | Task | File(s) | Est. | Test |
|---|------|---------|------|------|
| 1 | Data model: schema.sql + database.py init with WAL | shared/schema.sql, shared/database.py | 1h | test_database.py: CRUD operations, WAL concurrent read/write |
| 2 | Config system: .env + config.toml loader | shared/config.py | 30min | (covered by integration) |
| 3 | Regex message parser | bot/parser.py | 1h | test_parser.py: all 3 formats, edge cases (negative, decimal, missing fields) |
| 4 | FastAPI bot: /webhook endpoint, signature verification, message routing | bot/main.py, bot/feishu_client.py | 2h | test_api.py: webhook verification, message parse→reply flow |
| 5 | Streamlit auth: OAuth redirect + PIN fallback | web/auth.py | 1.5h | test_auth.py: PIN hash, session validation |
| 6 | Dashboard page: summary cards + category pie + week/month toggle | web/pages/dashboard.py, web/charts.py | 2h | Manual UI verification + data correctness check |
| 7 | Streamlit app.py: entry point, routing, session state | web/app.py | 1h | Integration: login→dashboard flow |
| 7b | PIN rate-limiting (exponential backoff: 2^attempt seconds) | web/auth.py | 15min | test_auth.py: rate-limit enforcement |

### P1 — Core features (next week)

| # | Task |
|---|------|
| 8 | Web expense form (fallback for non-Feishu users) |
| 9 | Budget settings page + threshold config |
| 10 | Budget alert (red highlight on dashboard when >80%) |
| 11 | Category management (CRUD custom categories) |

### P2 — Polish (deferred)
- Feishu weekly report push (Monday morning)
- Excel/CSV export
- LLM fuzzy parsing for messages
- DB migration framework

## Test Strategy

**Unit tests** (pytest + sqlite3):
- `test_parser.py`: Validate all 3 regex formats. Edge: "0.5 餐饮" (small amount), "128" (missing category), "abc 餐饮" (non-numeric), "-50 退款" (explicit refund), decimals with 1-2 places.
- `test_database.py`: Schema creation, CRUD on all 4 tables, WAL mode enabled, concurrent reads during write, foreign key enforcement.
- `test_privacy.py`: User A cannot query User B's individual expenses. Admin can see all. Family aggregate (totals by category, no per-user breakdown) visible to all members.
- `test_auth.py`: PIN hash verification, session token expiry, OAuth URL construction, rate-limit enforcement (exponential backoff).

**Empty-state tests** (critical — dashboard must not crash on empty data):
- `test_dashboard_empty.py`: Verify all chart functions return empty/placeholder output when no expenses exist (empty DataFrame → friendly message, not traceback).
- `test_budget_boundary.py`: Verify 0% budget, 79.999% threshold, division-by-zero when budget=0.

**Concurrency test** (critical — validates the two-process architecture):
- `test_wal_concurrency.py`: Write 50 expenses in one thread while reading dashboard aggregates in another. Assert no `OperationalError`, no data corruption, read returns consistent snapshot.

**Integration tests** (pytest + httpx):
- `test_api.py`: FastAPI TestClient → POST /webhook with valid/invalid signature, verify 200 response + correct reply message, idempotency (duplicate event_id rejected), URL verification challenge.
- `test_web.py`: Streamlit AppTest → login flow, dashboard data loads correctly, expense form submit → DB record created.

**Manual verification** (before ship):
- [ ] Bot: send "128 餐饮 午餐" → receive confirmation reply → check DB has record
- [ ] Bot: send "abc 餐饮" → receive "没识别出来" help message
- [ ] Web: login with PIN → see dashboard with correct data
- [ ] Web: verify privacy — user A cannot see user B's individual expenses (also covered by automated `test_privacy.py`)
- [ ] Dashboard: switch week/month → charts update correctly
- [ ] WAL: write via bot while reading via Streamlit → no lock errors

## Error & Rescue Registry

| Error Scenario | Detection | Rescue |
|---------------|-----------|--------|
| Bot receives duplicate event_id | Check DB for event_id before insert | Return 200, skip (Feishu retries) |
| Regex fails to parse message | parser returns None | Bot replies with help text showing correct format |
| SQLite file locked (extreme case) | sqlite3.OperationalError | Retry 3x with 100ms backoff, return 503 on failure |
| Feishu signature verification fails | HMAC mismatch | Return 401, log warning (potential attack) |
| OAuth code expired | Feishu token exchange fails | Redirect to re-auth, show friendly message |
| PIN login with wrong PIN | hash mismatch | Show "PIN incorrect", exponential backoff (2^attempt seconds) |
| Dashboard loaded with zero expenses | Empty DataFrame | Show friendly "还没有消费记录" placeholder, not a traceback |

## Security Hardening (in MVP scope)

- **PIN brute-force**: Exponential backoff — after N failed attempts, sleep 2^N seconds. Simple, effective, 10 lines.
- **XSS prevention**: All user-created strings (category names, display names) rendered via Streamlit built-in functions (no raw HTML injection). Streamlit's `st.write()` auto-escapes by default.
- **Feishu signature verification**: Constant-time HMAC comparison using `hmac.compare_digest()`.
- **CSRF on Streamlit forms**: Streamlit's built-in CSRF protection covers standard forms. No custom HTML forms in MVP.
- **Regex ReDoS prevention**: Anchor all regex patterns with `^...$`, use atomic groups where available, timeout wrapper on parse (100ms max).
- **Timezone**: All `recorded_at` timestamps stored in UTC. Dashboard aggregates in `Asia/Shanghai` timezone. Configurable via `TIMEZONE` env var.

## Deploy

Single VPS, two systemd services sharing one SQLite file:
- `family-expense-bot.service` → FastAPI :8000
- `family-expense-web.service` → `streamlit run web/app.py --server.port 8501`
- Nginx reverse proxy → domain + SSL (Let's Encrypt)
- Cron: daily SQLite backup to timestamped file

## Out of Scope (this plan)

- LLM-based fuzzy message parsing (Phase 2)
- Feishu weekly push notifications (Phase 2)
- Excel/CSV export (Phase 2)
- DB migration framework (Phase 2)
- Multi-tenant Feishu external contact handling
- External contact handling for cross-tenant Feishu users

## What Already Exists (reuse from easyworktool monorepo)

| Component | Source | How reused |
|-----------|--------|------------|
| Repository class | feishu-streamlit-verify/src/db/repository.py | Port directly, same pattern |
| Config loader (TOML + .env) | feishu-streamlit-verify/src/config.py | Port, strip material-specific sections |
| Feishu OAuth flow | feishu-streamlit-verify/src/auth/feishu_auth.py | Adapt: same app_id/secret flow, different redirect |
| Feishu API helpers | feishu-streamlit-verify/src/services/notify_service.py | Extract token management, message sending |
| Streamlit page pattern | feishu-streamlit-verify/app.py | Same sidebar nav + page routing pattern |
| i18n pattern | feishu-streamlit-verify/src/ui/i18n.py | Reuse pattern (Chinese-first, English optional) |

## Success Criteria (from design doc)

| Metric | Target |
|--------|--------|
| Expense entry | <10 seconds from Feishu message to confirmation reply |
| Dashboard load | <3 seconds page render |
| Budget warning | Red highlight when >80% monthly budget consumed |
| Family adoption | ≥3 users with 30-day activity |

## Dream State Delta

- **Current**: No family expense tracking. Expenses tracked ad-hoc or not at all.
- **This plan (MVP)**: Feishu Bot for frictionless entry, Streamlit dashboard for weekly/monthly insight, budget alerts. Single VPS deploy.
- **12-month ideal**: LLM fuzzy parsing ("中午和同事吃饭花了128" → auto-categorize), weekly push reports to family Feishu group, receipt photo OCR, multi-currency for travel, data export for tax season. Still the same two-process architecture, just richer.

## GSTACK REVIEW REPORT

### Review Scores

- **CEO**: SELECTIVE EXPANSION mode. Premises accepted with one caveat: Feishu adoption premise flagged for validation (see User Challenge below). Plan scope appropriate for MVP — no expansion or reduction needed.
- **CEO Voices**: Claude subagent flagged strategic concerns (Feishu dependency, WeChat/Alipay competition, unvalidated adoption premise). Codex unavailable — single-model review.
- **Design**: Streamlit-native patterns sufficient for MVP. Dashboard layout (cards → pie → trend) follows standard analytics hierarchy. No custom CSS/JS — low risk. States specified (empty: placeholder, error: friendly message, loading: spinner).
- **Design Voices**: Skipped — no dedicated design subagent. Design review done inline by primary reviewer.
- **Eng**: Architecture sound for MVP scale. Three critical gaps found and FIXED: PIN rate-limiting added, empty-state tests added, concurrency test added, privacy enforcement test added.
- **Eng Voices**: Claude subagent identified PIN brute-force (CRITICAL), privacy enforcement test gap (HIGH), missing concurrency test (HIGH), WAL unbounded growth (MEDIUM), ReDoS (MEDIUM), timezone (MEDIUM). All critical/high items addressed; medium items documented with mitigations.
- **DX**: Skipped — not a developer-facing product.

### Cross-Phase Themes

No cross-phase themes — each phase's concerns were distinct. The CEO flagged adoption risk; Eng flagged security/test gaps. No overlapping concerns between phases.

### Dual Voices Consensus Tables

**CEO Consensus:**
```
  Dimension                           Claude  Consensus
  ──────────────────────────────────── ─────── ─────────
  1. Premises valid?                   MIXED   Premise 1-5 accepted, premise 6 (Feishu adoption) flagged
  2. Right problem to solve?           PARTIAL Record-keeping vs behavior-change framing noted
  3. Scope calibration correct?        YES     MVP scope appropriate
  4. Alternatives sufficiently explored? NO     WeChat/Alipay not evaluated
  5. Competitive/market risks covered?  NO     Existing payment apps compete on zero-effort tracking
  6. 6-month trajectory sound?         YES     Architecture scales to P2 features
```
Codex unavailable. Claude subagent only — single-model review.

**Eng Consensus:**
```
  Dimension                           Claude  Consensus
  ──────────────────────────────────── ─────── ─────────
  1. Architecture sound?               YES     Two-process + WAL appropriate for family scale
  2. Test coverage sufficient?         NO → YES Critical gaps now filled (PIN rate-limit, empty-state, concurrency, privacy)
  3. Performance risks addressed?      PARTIAL WAL unbounded growth documented, mitigation noted
  4. Security threats covered?         NO → YES PIN brute-force, XSS, ReDoS, timing-safe HMAC all addressed
  5. Error paths handled?              YES     Error & Rescue Registry covers 6 scenarios
  6. Deployment risk manageable?       YES     Two systemd services, no migration risk (greenfield)
```
Codex unavailable. Claude subagent only — single-model review.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Mode: SELECTIVE EXPANSION | Mechanical | P3 | MVP scope already well-defined by design doc | SCOPE EXPANSION, HOLD SCOPE |
| 2 | CEO | Accept premises 1-5 | Mechanical | P6 | Premises grounded in technical reality (SQLite capacity, multi-user model) | None |
| 3 | CEO | Flag premise 6 (Feishu adoption) | User Challenge | — | Both model and reviewer agree adoption should be validated before building | Auto-accept |
| 4 | CEO | No scope expansion | Mechanical | P3 | Existing scope hits MVP target; expansions deferred to P1/P2 | Expand to WeChat/MCP |
| 5 | Eng | Add PIN rate-limiting to MVP | Mechanical | P1 | Security gap that's cheap to fix (10 lines); completeness principle demands it | "no rate limit in MVP" |
| 6 | Eng | Add empty-state + concurrency tests | Mechanical | P1/P2 | Dashboard crash on empty data is a 2am bug; concurrency validates core architecture | Defer tests |
| 7 | Eng | Add privacy enforcement test | Mechanical | P1 | Privacy is the core data model invariant — untested means broken | Manual-only verification |
| 8 | Eng | Architecture: two-process + WAL | Mechanical | P5 | Explicit shared-db simpler than message queue for 8-user family | Message queue, separate DBs |
| 9 | Eng | Test plan: all codepaths mapped | Mechanical | P1 | Every new codepath has a test row in the test plan | None |
| 10 | Design | Streamlit-native patterns over custom UI | Mechanical | P5 | 10-line Streamlit widget > 200-line custom React component | Custom CSS/JS framework |

### Changes Made to Plan

1. **PIN rate-limiting added** — task 7b in P0, 15min. Exponential backoff (2^attempt seconds).
2. **Empty-state tests added** — test_dashboard_empty.py, test_budget_boundary.py.
3. **Concurrency test added** — test_wal_concurrency.py validates two-process architecture.
4. **Privacy enforcement test added** — test_privacy.py validates the core data model invariant.
5. **Security hardening section added** — XSS, ReDoS, timing-safe HMAC, timezone handling.
6. **PIN no-rate-limit exclusion removed** from Out of Scope.

### Deferred to TODOS.md

- Feishu adoption validation (ask 3 family members before building)
- WeChat-friendly entry (Phase 2 consideration)
- WAL auto-checkpointing configuration
- DB migration framework (Phase 2)
- LLM fuzzy parsing (Phase 2)
- Excel/CSV export (Phase 2)
- Feishu weekly push notifications (Phase 2)

### Test Plan Artifact

Written to: `~/.gstack/projects/skyshenzhen-easyworktool/shaver-main-test-plan-20260518-181500.md`
