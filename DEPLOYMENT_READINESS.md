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

## 5. Operational Health & Diagnostics

Distinct liveness and readiness probes are exposed via `src/platform/server.py`:

- **Liveness Endpoint (`/health/liveness`):** Confirms process execution health (`200 OK`).
- **Readiness Endpoint (`/health/readiness`):** Verifies configuration validity, provider health, and persistence storage integrity (`200 OK` or `503 Service Unavailable`).
- **Diagnostics Endpoint (`/api/v1/diagnostics`):** Exposes safe operational diagnostics.
- **Request Correlation:** Generates unique request correlation identifiers (`req_<hex>`) for audit tracking.

---

## 6. Public HTTPS Deployment Requirements

To perform a live public HTTPS deployment to remote cloud infrastructure, the following external items are required:

1. **Cloud Compute / Host Provisioning** (e.g. AWS EC2, GCP Compute Engine, DigitalOcean Droplet, Render, Fly.io, or Kubernetes cluster).
2. **Domain Name & DNS A/AAAA Records** pointing to host IP.
3. **TLS/SSL Certificate Termination** (e.g. Nginx/Caddy reverse proxy with Let's Encrypt or Cloudflare TLS).
4. **Environment Secrets Provisioning** (`SESSION_SECRET`, `INITIAL_ADMIN_PASSWORD`, `ALLOWED_ORIGINS`).
