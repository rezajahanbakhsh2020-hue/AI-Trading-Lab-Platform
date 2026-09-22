# Deployment Readiness & Security Contract — Project 2 (AI-Trading-Lab-Platform)

## Overview

Project 2 operates as the presentation, application, and integration host for Project 1.
This document outlines the repository-side deployment contract, security guarantees, configuration requirements, operational readiness criteria, and automated release validation for production runtime deployment.

> **Deployment Disclosure:** This repository is fully pre-configured and hardened for containerized or bare-metal HTTPS deployment using `src/platform/server.py` or `Dockerfile`. Real public HTTPS deployment requires infrastructure deployment (e.g. cloud provider instance, domain DNS pointing, reverse proxy / SSL certificate).

---

## 1. Production Server Entry Point & Start Commands

The production runtime is served by `src.platform.server`.

### Native Start Command
```bash
# 1. Compile SPA Frontend Assets
cd web && npm ci && npm run build && cd ..

# 2. Run Production Web Application Server
APP_ENV=production \
PUBLIC_BASE_URL="https://trade.yourdomain.com" \
SESSION_SECRET="<YOUR_32_CHAR_RANDOM_SESSION_SECRET>" \
INITIAL_ADMIN_PASSWORD="<YOUR_SECURE_INITIAL_ADMIN_PASSWORD>" \
ALLOWED_ORIGINS="https://trade.yourdomain.com" \
python -m src.platform.server
```

### Docker Start Command
```bash
docker compose up --build -d
```

---

## 2. Runtime Configuration & Environment Secrets

Production settings are enforced via `src/platform/config.py` (`PlatformConfig`).
In production (`APP_ENV=production`), missing critical secrets or unprovisioned Owner accounts fail closed immediately at startup.

| Environment Variable | Required in Prod | Description & Example |
|---|---|---|
| `APP_ENV` | Yes | Set to `production` (or `development` / `testing`). |
| `PUBLIC_BASE_URL` | **YES** | Explicit public HTTPS/HTTP base URL of the Project 2 deployment reachable by external Project 1 producers (e.g., `https://trade.yourdomain.com`). Rejects `localhost` in production. |
| `SESSION_SECRET` | **YES** | Strong random secret string (min 32 characters). Default dev secret is rejected in production. |
| `INITIAL_ADMIN_PASSWORD` | **YES** | Operator-supplied bootstrap password for initial Owner account (`admin_owner`). Production fails startup if unprovisioned and this is missing. |
| `ALLOWED_ORIGINS` | **YES** | Comma-separated trusted origin URLs (e.g., `https://trade.yourdomain.com`). |
| `RECOVERY_EMAIL` | Optional | Designated permanent Owner/Admin recovery email contact. |
| `PERSISTENCE_DIR` | Optional | Directory path for file-backed JSON user/session repository (default `.data`). |
| `SESSION_MAX_AGE_SECONDS` | Optional | Maximum active session duration in seconds (default `86400`). |
| `ENABLE_HTTPS_REDIRECT` | Optional | Set `true` to enforce Strict-Transport-Security (HSTS) headers. |

---

## 3. Automated Release Verification & End-to-End Validation

The platform includes an end-to-end Release Validation Harness (`tests/test_release_validation_harness.py`) and CI workflow integration (`.github/workflows/main.yml`) that verifies the assembled application before release.

### Command to Execute Release Verification Harness
```bash
PYTHONPATH=. pytest tests/test_release_validation_harness.py -v
```

### Automated Release Validation Scope (Categories A–L)
- **A. Application Startup:** Environment variable requirements, fail-closed behavior on missing production secrets, persistence directory binding, security headers (`X-Frame-Options`, `X-Content-Type-Options`, HSTS).
- **B. Health & Readiness:** Liveness (`/health/liveness`) and deep readiness (`/health/readiness`) probing, subsystem health classifications (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `NOT_CONFIGURED`).
- **C. Authentication & Account Lifecycle:** Salted PBKDF2 password authentication, SHA-256 hashed session token issuance, active session validation, session logout revocation, account activation/expiration lifecycle enforcement.
- **D. RBAC & IDOR Defense:** Permanent Owner immunity, Admin customer management, Customer workspace isolation, IDOR attempt rejections, privilege escalation resistance.
- **E. Persistence & Restart Integrity:** State persistence across server process restarts using atomic JSON writes.
- **F. Project 1 Integration Gateway:** Versioned contract validation (`1.0`, `v1.0` accepted; `2.0` rejected with status 422), non-calculation guarantees, user-isolated integration records.
- **G. Execution Gateway Boundary:** Fail-closed non-execution policy (`externally_executed=False`), Order Intent lifecycle tracking, idempotency/replay protection.
- **H. Notification System:** Canonical event creation, user preferences persistence, delivery state reporting (`EXTERNAL_NOT_CONFIGURED` when credentials are unprovisioned).
- **I. AI Gateway & Provider Boundary:** Truthful provider status reporting (`not_configured`, `available`), URL validation / SSRF protection, secret sanitization.
- **J. Observability & Correlation:** Unique request correlation ID generation (`req_<hex>`) and propagation.
- **K. Frontend SPA Serving:** Production Vite bundle serving (`web/dist`), SPA route fallback (`/intents`, `/health`, etc.), directory traversal attack defense (`/../../../../etc/passwd`).
- **L. Persistence Backup & Recovery:** Atomic JSON snapshot creation, SHA-256 manifest verification, non-destructive restore, post-recovery readiness stability.

---

## 4. Security Boundaries & Fail-Closed Behavior

- **Zero Hardcoded Credentials:** Plaintext production passwords and reusable Owner keys are strictly prohibited in production code paths.
- **Session Token Hashing:** Active session tokens are hashed using SHA-256 before storage or file persistence. Raw tokens are never written to disk or logs.
- **Controlled Persistence Failures:** Corrupt user or session files raise explicit `CorruptStorageError` exceptions and degrade system readiness rather than silently swallowing errors or populating insecure defaults.
- **Permanent Owner/Admin Immunity:** Owner accounts (`admin_owner` / `admin`) are protected from expiration or customer lifecycle deactivation.
- **Server-Side Authorization & RBAC:** Every protected path and API call re-evaluates `is_account_valid()` in real-time. Owner accounts hold supreme authority, Admins can manage Customer accounts, and Customers are restricted to personal workspace capabilities.
- **Role Assignment & Session Revocation:** Owners can assign/revoke any role. Admins cannot promote users to Owner/Admin nor modify other Admins. Admins and users can revoke active session tokens, immediately invalidating access.
- **User Workspace Isolation & IDOR Protection:** Customer workspaces and watchlists are strictly isolated by authenticated user identity. Cross-user data access attempts raise explicit permission errors and generate security audit records.
- **File-Backed Workspace Persistence:** User workspaces, watchlists, active symbols, and chart/layout preferences persist across process restarts using atomic JSON writes (`FileBackedWorkspaceRepository`).
- **Expired/Inactive Access Denial:** Expired, future-starting, or deactivated accounts fail closed with sanitized error messages.
- **Secret Redaction:** Strategy code, proprietary indicators, exchange API keys, and session secrets are automatically sanitized by `SecretSanitizer` from logs, UI state, and audit records.
- **Execution Boundary:** External broker order execution is permanently disabled (`externally_executed=False`).

---

## 5. Structured User-Facing Error Experience & Help Center

- **Structured Operational Error Banner:** Every user-facing operational error displays WHAT happened, WHY it happened, WHAT the user can do now, WHAT to do if it continues, and a safe Reference Correlation ID.
- **In-App Help & Onboarding Center:** Full contextual documentation, getting started guides, subsystem explanations, status badge references, and troubleshooting paths available under route `/help`.
- **Localization:** 100% translated across English (EN), Persian (FA RTL), Arabic (AR RTL), and Turkish (TR LTR).

---

## 6. Operational Health, Readiness States & Diagnostics

Distinct liveness and readiness probes are exposed via `src/platform/server.py`:

- **Liveness Endpoint (`/health/liveness`):** Confirms process execution health (`200 OK`).
- **Readiness Endpoint (`/health/readiness`):** Performs deep evaluation across subsystems (`200 OK` or `503 Service Unavailable`).
- **Subsystem State Classifications:**
  - `HEALTHY`: Subsystem is fully operational and configured.
  - `DEGRADED`: Non-critical subsystem issue present, but overall platform remains functional.
  - `UNAVAILABLE`: Critical subsystem component failure rendering service unusable.
  - `NOT_CONFIGURED`: Optional integration or credential not provisioned (e.g. Project 1 Gateway or Telegram bot tokens).
- **Diagnostics Endpoint (`/api/v1/diagnostics`):** Exposes safe operational diagnostics with secret redaction.
- **Request Correlation:** Generates unique request correlation identifiers (`req_<hex>`) for audit tracking.

---

## 7. Project 1 ↔ Project 2 Integration Gateway Contract & Security Architecture

The platform provides a versioned, authenticated, auditable Hexagonal Integration Gateway (`src/platform/services/project1_gateway.py` and `src/platform/domain/project1_contract.py`) for Project 1 signal output ingestion and lifecycle management.

### Boundary Principles & Non-Calculation Guarantee
- **Project 1 Source of Truth:** Project 1 is the sole source of truth for all strategy decisions, signals, Entry prices, Stop Loss (SL), Take Profit levels (TP1/TP2/TP3), and Trailing Stop configurations.
- **Non-Calculation & Non-Modification:** Project 2 NEVER calculates, modifies, optimizes, or decides strategy rules, prices, or trade parameters. Project 2 strictly validates, authorizes, scopes, persists, and presents them.
- **Contract Versioning:** All integration payloads specify a contract version. Supported versions include `1.0`, `1.0.0`, and `v1.0`. Payloads with unsupported versions (e.g. `2.0`) are explicitly rejected with status `422` (`UNSUPPORTED_CONTRACT_VERSION`).

### Integration Gateway API Endpoints
- **Contract Capabilities Discovery (`GET /api/v1/integration/project1/capabilities`):** Exposes supported contract versions, command types, signal types, lifecycle states, and non-calculation guarantees.
- **Authorized Signal Ingestion (`POST /api/v1/integration/project1/ingest`):** Authenticates the caller, verifies `signals:write` RBAC authorization, validates the contract schema, enforces user/tenant isolation, checks replay protection, generates correlation IDs, persists the record, and logs an audit event.
- **Lifecycle Transition Command (`POST /api/v1/integration/project1/lifecycle`):** Updates signal lifecycle states (`STAGED`, `ACTIVE`, `UPDATED`, `CANCELLED`, `EXPIRED`, `REJECTED`, `EXECUTED`) with audit control logging.
- **User-Isolated Integration Records (`GET /api/v1/integration/project1/records`):** Retrieves user-scoped integration records. Non-admin users are strictly isolated to their own records.

---

## 8. Notification & Event Delivery Layer Architecture

The notification layer provides canonical, user-scoped event processing and multi-channel delivery support.

### Event Model & Notification Categories
- **Canonical Notification Categories:** `signal`, `project1_integration`, `signal_lifecycle`, `market_health`, `workspace`, `system`, `security`, `account_session`, and `admin`.
- **Event Integrity:** Every `NotificationEvent` includes `event_id`, `event_type`, `category`, `severity`, `title`, `message`, `timestamp`, `target_user_id`, `payload`, `version`, `source`, `correlation_id`, and `status`.

### User Notification Preferences & Persistence
- User-scoped preferences (`NotificationPreferences`) are integrated into `Workspace` entities and persisted across server restarts (`FileBackedWorkspaceRepository`).
- Users can enable/disable categories, toggle in-app vs. external delivery, and set minimum severity thresholds.

### Telegram-Ready Delivery Port & Status Classification
- **Ports & Adapters Architecture:** Outbound notifications are routed via `NotificationDeliveryPort` and `TelegramDeliveryPort`.
- **Honest Delivery Statuses:** Explicitly distinguishes `IN_APP_AVAILABLE`, `EXTERNAL_CONFIGURED`, `EXTERNAL_NOT_CONFIGURED`, `DELIVERY_FAILED`, and `DELIVERY_UNAVAILABLE`.
- **Zero Fake Delivery Claims:** Telegram delivery reports `UNCONFIGURED_CREDENTIALS` and `externally_delivered=False` when bot tokens are not configured in the environment.

---

## 9. Public HTTPS Deployment Requirements & External Boundaries

To perform a live public HTTPS deployment to remote cloud infrastructure, the following external items remain intentionally external:

1. **Cloud Compute / Host Provisioning** (e.g. AWS EC2, GCP Compute Engine, DigitalOcean Droplet, Render, Fly.io, or Kubernetes cluster).
2. **Domain Name & DNS A/AAAA Records** pointing to host IP.
3. **TLS/SSL Certificate Termination** (e.g. Nginx/Caddy reverse proxy with Let's Encrypt or Cloudflare TLS).
4. **Environment Secrets Provisioning** (`SESSION_SECRET`, `INITIAL_ADMIN_PASSWORD`, `ALLOWED_ORIGINS`).
5. **Real Exchange / Broker Accounts & Credentials** (Order execution remains non-external and fail-closed by design).

---

## 10. Execution Gateway & Order Intent Persistence Layer

The platform provides persistent storage and authenticated REST endpoints for managing Order Intents and Execution Gateway operations.

### Operational Safety & Non-Execution Contract
- **Fail-Closed Execution Boundary:** `externally_executed=False` is permanently enforced across all execution attempts and reconciliation records.
- **Zero False Execution Claims:** Project 2 never claims broker order routing, fills, or position creation.
