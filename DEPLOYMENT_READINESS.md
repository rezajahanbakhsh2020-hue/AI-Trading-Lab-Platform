# Deployment Readiness & Security Contract — Project 2 (AI-Trading-Lab-Platform)

## Overview

Project 2 operates as the presentation, application, and integration host for Project 1.
This document outlines the repository-side deployment contract, security guarantees, configuration requirements, and operational readiness criteria for future real HTTPS web deployment.

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
SESSION_SECRET="production_super_secret_session_key_32_chars_min_2026!" \
INITIAL_ADMIN_PASSWORD="ProductionAdminPassword2026!" \
ALLOWED_ORIGINS="https://yourdomain.com" \
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
| `SESSION_SECRET` | **YES** | Strong random secret string (min 32 characters). Default dev secret is rejected in production. |
| `INITIAL_ADMIN_PASSWORD` | **YES** | Operator-supplied bootstrap password for initial Owner account (`admin_owner`). Production fails startup if unprovisioned and this is missing. |
| `ALLOWED_ORIGINS` | **YES** | Comma-separated trusted origin URLs (e.g., `https://trade.yourdomain.com`). |
| `RECOVERY_EMAIL` | Optional | Designated permanent Owner/Admin recovery email contact. |
| `PERSISTENCE_DIR` | Optional | Directory path for file-backed JSON user/session repository (default `.data`). |
| `SESSION_MAX_AGE_SECONDS` | Optional | Maximum active session duration in seconds (default `86400`). |
| `ENABLE_HTTPS_REDIRECT` | Optional | Set `true` to enforce Strict-Transport-Security (HSTS) headers. |

---

## 3. Security Boundaries & Fail-Closed Behavior

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

## 4. Structured User-Facing Error Experience & Help Center

- **Structured Operational Error Banner:** Every user-facing operational error displays WHAT happened, WHY it happened, WHAT the user can do now, WHAT to do if it continues, and a safe Reference Correlation ID.
- **In-App Help & Onboarding Center:** Full contextual documentation, getting started guides, subsystem explanations, status badge references, and troubleshooting paths available under route `/help`.
- **Localization:** 100% translated across English (EN), Persian (FA RTL), Arabic (AR RTL), and Turkish (TR LTR).

---

## 5. Operational Health, Readiness States & Diagnostics

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

## 5.1 Real Smoke & End-to-End Verification

Automated production smoke verification can be executed at any time using:

```bash
PYTHONPATH=. pytest tests/test_smoke_runtime_verification.py
```

The smoke test suite verifies:
1. Application startup under `APP_ENV=production`.
2. Liveness (`/health/liveness`) and HSTS/Security headers.
3. Deep readiness probe (`/health/readiness`) and subsystem health state classification.
4. Operational diagnostics (`/api/v1/diagnostics`) secret redaction.
5. Production SPA static asset serving (`web/dist`) and directory traversal attack defense (`/../../../../etc/passwd`).
6. End-to-end authentication, RBAC authorization, customer workspace persistence (`/api/v1/workspace`), and recovery diagnostics (`/api/v1/operational/recovery`).
7. Signal-handled graceful server shutdown (`SIGTERM` / `SIGINT`).

---

## 6. Project 1 ↔ Project 2 Integration Gateway Contract & Security Architecture

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

### Security, Customer Isolation, & Idempotency
- **IDOR Protection:** Cross-tenant or cross-user payload injections are rejected (`FORBIDDEN_USER_MISMATCH`) and recorded as security audit events.
- **Replay Protection / Idempotency:** Duplicate signal submissions with the same `(user_id, signal_id)` return an idempotent acceptance response (`DUPLICATE_ACCEPTED`) without duplicating records or audit events.
- **File-Backed Persistence:** Integration records persist across restarts in `data/project1_integration_records.json` using atomic temporary file replacements (`FileBackedProject1IntegrationRepository`).
- **Audit Logging:** Every capability discovery, signal ingestion, schema rejection, IDOR attempt, and lifecycle update is logged to `PlatformAuditControlService` with secret sanitization.

---

## 7. Notification & Event Delivery Layer Architecture

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

### Security, Isolation, & Audit
- **Strict Server-Side Isolation:** Users cannot access or trigger notifications for other users (raises IDOR / `PermissionError`).
- **Secret Sanitization:** Protected strategy parameters and secrets are automatically redacted before inbox storage or delivery.
- **Audit Logging:** Ingestion, delivery attempts, and preference updates generate `PlatformAuditControlService` records.

---

## 8. Public HTTPS Deployment Requirements

To perform a live public HTTPS deployment to remote cloud infrastructure, the following external items are required:

1. **Cloud Compute / Host Provisioning** (e.g. AWS EC2, GCP Compute Engine, DigitalOcean Droplet, Render, Fly.io, or Kubernetes cluster).
2. **Domain Name & DNS A/AAAA Records** pointing to host IP.
3. **TLS/SSL Certificate Termination** (e.g. Nginx/Caddy reverse proxy with Let's Encrypt or Cloudflare TLS).
4. **Environment Secrets Provisioning** (`SESSION_SECRET`, `INITIAL_ADMIN_PASSWORD`, `ALLOWED_ORIGINS`).

---

## 9. Professional Financial Charting & Visual Boundary Architecture

The platform embeds TradingView Lightweight Charts (`lightweight-charts` v5.2.1, Apache-2.0 open-source license) as its primary financial visualization foundation (`web/src/ui/components/InteractiveChart.tsx`).

### Architectural Principles & Licensing Rationale
- **Apache-2.0 License Compatibility:** Lightweight Charts is an open-source, high-performance HTML5 Canvas chart engine designed for financial applications.
- **Zero Proprietary/Paid Dependencies:** No proprietary TradingView widgets or paid external market data APIs are introduced.
- **Mobile-First Responsive Layout:** Fluid `ResizeObserver` auto-scaling supports viewports from 360px, 390px, 430px portrait to full-screen desktop without horizontal overflow or clipped controls.

### Chart Capabilities & Data Flow
- **Multi-Series Support:** Dynamic switching between Candlestick, Line, and Area chart views.
- **Volume Histogram Pane:** Dedicated histogram volume pane synchronized with the price time scale.
- **Crosshair Legend & Tooltip:** Real-time crosshair inspection feeding OHLCV status indicators.
- **Data Truthfulness Overlays:** Explicit visual state indicators for `connected`, `disconnected`, `loading`, `stale`, and `error` states without fake candles or fabricated price feeds.

### Project 1 Visualization Boundary
- **Read-Only Level Rendering:** Entry, Stop Loss (SL), and Take Profit (TP1, TP2, TP3) levels from authorized Project 1 contracts are rendered as styled price lines (`createPriceLine`).
- **Signal Event Markers:** Project 1 signal actions are rendered as explicit arrow markers (`createSeriesMarkers`).
- **Strict Non-Calculation Contract:** Project 2 NEVER calculates, alters, infers, or replaces Project 1 strategy outputs or price levels.
