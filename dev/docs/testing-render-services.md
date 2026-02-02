# Testing Render Services

## Why "Backend API at http://localhost:8000 is not accessible"

The **NotebookLLM frontend** (Chat/Studio UI) calls the agent API using a URL that is **baked at build time**. If that URL is not set when the image is built, it defaults to `http://localhost:8000`, so the deployed UI keeps trying to reach localhost and fails.

**Fix:** Rebuild the frontend with the deployed API URL.

- **Notebookllm (frontend) service on Render:** Set **Environment** → **API_BASE_URL** = `https://sparksbm-agent.onrender.com` (or your actual NotebookLLM API URL). Then **Manual Deploy** so the image is rebuilt. Render turns env vars into Docker build args automatically.
- **SparksBM-Web (ISMS dashboard with chatbot):** Set **NOTEBOOKLLM_API_URL** = `https://sparksbm-agent.onrender.com` and redeploy.

The Dockerfiles now accept these as build args.

## Test failures (timeout / 404)

- **Keycloak, SparksBM-API timeout:** Free-tier instances sleep after ~15 min. First request can take 50–90s. Run the test again with `--timeout 90` or wait 1–2 min and refresh in the browser.
- **NotebookLLM-UI 404:** The default test URL may not match your Render slug. Get the exact URL from the Render dashboard (click the **Notebookllm** service → copy the URL) and set `NOTEBOOKLLM_UI_URL` when running the test, or ignore if the UI works in the browser.

## Get your service URLs

In **Render Dashboard** → click each **service name** → the service page shows the **URL** (e.g. `https://keycloak-server.onrender.com`). Use that exact URL; the slug is fixed when the service is created.

## Run the test script

```bash
# From repo root
cd /path/to/SparksBM

# Optional: set URLs if they differ from defaults (see script header)
export KEYCLOAK_URL=https://keycloak-server.onrender.com
export SPARKSBM_WEB_URL=https://sparksbm-web.onrender.com
export SPARKSBM_API_URL=https://sparksbm.onrender.com
export NOTEBOOKLLM_API_URL=https://sparksbm-agent.onrender.com
export NOTEBOOKLLM_UI_URL=https://notebookllm-w3w7.onrender.com

python dev/test/test_render_services.py
```

First run can take **50–90 seconds** per service on free tier (instances spin down after ~15 min inactivity).

## Test a single service (e.g. NotebookLLM API for prompt tests)

```bash
python dev/test/test_render_services.py --api-url https://YOUR-NOTEBOOKLLM-API.onrender.com
```

## Manual checks

| Service        | URL (example)                    | What to try |
|----------------|----------------------------------|-------------|
| Keycloak       | https://keycloak-server.onrender.com | Open in browser → admin console or realm |
| SparksBM-Web   | https://sparksbm-web.onrender.com    | Open in browser → login (needs Keycloak) |
| SparksBM-API   | https://sparksbm.onrender.com        | `curl https://.../actuator/health` or API path |
| NotebookLLM-API| https://sparksbm-agent.onrender.com   | `curl https://.../api/agent/tools` |
| NotebookLLM-UI | (from dashboard)                     | Open in browser |

If you see a blank page or "Application failed to load", wait 1–2 minutes and refresh (cold start).
