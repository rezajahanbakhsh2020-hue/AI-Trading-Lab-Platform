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

### Containerized Production Deployment (Docker / Compose)

```bash
docker compose up --build -d
```
