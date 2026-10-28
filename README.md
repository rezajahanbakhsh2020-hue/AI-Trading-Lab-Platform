# AI-Trading-Lab-Platform

Host, presentation, and application layer for AI-Trading-Lab.

Project 1 remains the strategy and decision engine. This repository does not generate trading intelligence or execute orders.

## Host application & Local Development

The visual host lives in `web/`.

```bash
cd web
npm install
npm run dev
```

## Production Application Server

The production-ready web application server entry point is provided in `src/platform/server.py`.

### Quick Start (Local Production Server)

1. Build the SPA frontend bundle:
   ```bash
   cd web && npm ci && npm run build && cd ..
   ```

2. Launch the application server:
   ```bash
   APP_ENV=production \
   SESSION_SECRET="production_super_secret_session_key_32_chars_min_2026!" \
   INITIAL_ADMIN_PASSWORD="ProductionAdminPassword2026!" \
   ALLOWED_ORIGINS="http://localhost:8000" \
   python -m src.platform.server
   ```

3. Access the application in browser: `http://localhost:8000`

### One-Command Local Workflow (Termux-compatible)

`scripts/run_local_platform.sh` starts the platform on a loopback port with an
EPHEMERAL, in-memory service key generated for that single run (never stored on
disk, logged, or committed), then runs the local publication proof:

```bash
sh scripts/run_local_platform.sh                # build SPA, start server, run proof
sh scripts/run_local_platform.sh --skip-proof   # just build + serve
```

Environment overrides: `PORT`, `HOST`, `PERSISTENCE_DIR`, `PROOF_SYMBOL`,
`PROOF_TIMEFRAME`, `PROOF_DECISION`.

The proof (`scripts/verify_local_signal_path.py`) publishes a Contract v1.0
payload through the real authenticated HTTP ingest endpoint and verifies the
record becomes visible through the real snapshot path, reporting the observed
action/timeframe/risk levels. It fails closed when no ephemeral credential is
available. Isolated persistence directories keep proof runs out of the owner's
production `.data/` store.

### Containerized Production Deployment (Docker / Compose)

```bash
docker compose up --build -d
```
