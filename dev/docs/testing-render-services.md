# Testing Render Services

## Your actual Render services (checked via Render MCP)

| Service name (dashboard) | URL | Service ID |
|---------------------------|-----|------------|
| SparksBM-API | https://sparksbm.onrender.com | srv-d5vi6biqcgvc739lcrm0 |
| keycloak-server | https://keycloak-server-5xv3.onrender.com | srv-d6084pali9vc73aq9udg |
| Notebookllm-API | https://sparksbm-agent.onrender.com | srv-d5vi4tiqcgvc739lb9vg |
| SparksBM-Web | https://sparksbm-web.onrender.com | srv-d6040p14tr6s73a78dng |
| Notebookllm | https://notebookllm-aukc.onrender.com | srv-d607vukhg0os73a4miog |

Env vars were set via Render MCP to use these URLs (Keycloak: keycloak-server-5xv3, Java API: sparksbm). Deploys were triggered for all five services.

---

## Environment variables for all Render services

Use this as a checklist in the Render dashboard. **Your live URLs** (above) differ from blueprint names: use **sparksbm.onrender.com** for the Java backend and **keycloak-server-5xv3.onrender.com** for Keycloak.

### 1. SparksBM-API (Java Backend / ISMS API) – *your service: sparksbm.onrender.com*

| Key | Value |
|-----|--------|
| SPRING_DATASOURCE_URL | jdbc:postgresql://ep-young-bread-a1f8nuq1-pooler.ap-southeast-1.aws.neon.tech/SparksBM?sslmode=require |
| SPRING_DATASOURCE_USERNAME | neondb_owner |
| SPRING_DATASOURCE_PASSWORD | npg_UYhru41qVIZS |
| KEYCLOAK_AUTH_SERVER_URL | https://${KEYCLOAK_HOST} (or https://keycloak-server-5xv3.onrender.com) |
| SPRING_SECURITY_OAUTH2_ISSUER_URI | https://keycloak-server-5xv3.onrender.com/realms/sparksbm |
| SPRING_SECURITY_OAUTH2_JWK_SET_URI | https://keycloak-server-5xv3.onrender.com/realms/sparksbm/protocol/openid-connect/certs |
| VEO_CORS_ORIGINS | https://sparksbm-web.onrender.com |
| SPRING_RABBITMQ_HOST | (if using queue: fromService sparksbm-queue) |

**URL:** https://sparksbm.onrender.com

---

### 2. keycloak-server (Keycloak) – *your service: keycloak-server-5xv3.onrender.com*

**One-time: create the sparksbm realm and client.** Keycloak starts with only the `master` realm. The app expects a realm **sparksbm** and a client **sparksbm** (and user `admin@sparksbm.com`). Run once from your machine (with Keycloak reachable):

```bash
cd SparksbmISMS/keycloak
KEYCLOAK_URL=https://keycloak-server-5xv3.onrender.com \
KEYCLOAK_ADMIN=admin \
KEYCLOAK_ADMIN_PASSWORD=admin123 \
python create-sparksbm-realm.py
```

Then in Keycloak Admin → **Manage realms** you should see **sparksbm**; in **Clients** (after switching to realm sparksbm) you should see **sparksbm**.

| Key | Value |
|-----|--------|
| KC_DB | postgres |
| KC_DB_URL | jdbc:postgresql://ep-young-bread-a1f8nuq1-pooler.ap-southeast-1.aws.neon.tech/keycloak?sslmode=require |
| KC_DB_USERNAME | neondb_owner |
| KC_DB_PASSWORD | npg_UYhru41qVIZS |
| KC_HOSTNAME | keycloak-server-5xv3.onrender.com |
| KC_PROXY_HEADERS | xforwarded |
| KEYCLOAK_ADMIN | admin |
| KEYCLOAK_ADMIN_PASSWORD | admin123 |

**URL:** https://keycloak-server-5xv3.onrender.com

---

### 3. Notebookllm-API (NotebookLLM API) – *your service: sparksbm-agent.onrender.com*

| Key | Value |
|-----|--------|
| API_PORT | 8000 |
| GEMINI_API_KEY | (set in Render – secret) |
| CORS_ORIGINS | https://notebookllm-aukc.onrender.com,https://sparksbm-web.onrender.com |
| VERINICE_API_URL | https://sparksbm.onrender.com |
| KEYCLOAK_URL | https://keycloak-server-5xv3.onrender.com |
| KEYCLOAK_REALM | sparksbm |
| SPARKSBM_USERNAME | admin@sparksbm.com |
| SPARKSBM_PASSWORD | admin123 |

**URL:** https://sparksbm-agent.onrender.com

---

### 4. SparksBM-Web (ISMS dashboard)

| Key | Value |
|-----|--------|
| NOTEBOOKLLM_API_URL | https://sparksbm-agent.onrender.com |
| VEO_DEFAULT_API_URL | https://sparksbm.onrender.com |
| VEO_OIDC_URL | https://keycloak-server-5xv3.onrender.com/auth |
| VEO_OIDC_REALM | sparksbm |
| VEO_OIDC_CLIENT | sparksbm |
| VEO_ACCOUNT_PATH | https://keycloak-server-5xv3.onrender.com/auth/realms/sparksbm/account |
| VEO_OIDC_ACCOUNT_APPLICATION | https://keycloak-server-5xv3.onrender.com/auth/realms/sparksbm/account |

**URL:** https://sparksbm-web.onrender.com  
**Note:** These are used at **build time**. After changing any value, trigger a **Manual Deploy** so the image is rebuilt.

---

### 5. sparksbm-queue (RabbitMQ)

No environment variables required for the default image.

---

### 6. Notebookllm (standalone Chat/Studio frontend) – *your service: notebookllm-aukc.onrender.com*

| Key | Value |
|-----|--------|
| API_BASE_URL | https://sparksbm-agent.onrender.com |

**URL:** https://notebookllm-aukc.onrender.com  
**Note:** Set before build and redeploy so the UI calls the deployed API.

---

## Redirect loop and empty unit/domain on ISMS dashboard

If the ISMS dashboard (SparksBM-Web) shows **"Redirecting..."** forever and **"Select unit" / "Select domain"** are empty, the frontend was built without the deployed **API** and **Keycloak** URLs. Those are baked at build time.

**Fix:** Set these **environment variables** for **SparksBM-Web** in Render (then redeploy so the image is rebuilt):

- **VEO_DEFAULT_API_URL** = `https://<your-java-backend>.onrender.com` (e.g. `https://sparksbm-core.onrender.com`; add `/veo` only if your backend uses that context path)
- **VEO_OIDC_URL** = `https://<your-keycloak>.onrender.com/auth` (e.g. `https://sparksbm-auth.onrender.com/auth`)
- **VEO_OIDC_REALM** = `sparksbm`
- **VEO_OIDC_CLIENT** = `sparksbm`
- **VEO_ACCOUNT_PATH** = `https://<keycloak>/auth/realms/sparksbm/account`
- **VEO_OIDC_ACCOUNT_APPLICATION** = same as VEO_ACCOUNT_PATH

If your Render service names differ (e.g. `keycloak-server`, `SparksBM-API`), use those hosts in the URLs above.

## "ISMS client not available" in chat

The agent (NotebookLLM API) needs to reach the ISMS backend and Keycloak. Set these for the **NotebookLLM-API / sparksbm-agent** service:

- **VERINICE_API_URL** = `https://<your-java-backend>.onrender.com`
- **KEYCLOAK_URL** = `https://<your-keycloak>.onrender.com`

Then redeploy the agent. The chat widget error text no longer hardcodes localhost.

## Why "Backend API at http://localhost:8000 is not accessible"

The **NotebookLLM frontend** (Chat/Studio UI) calls the agent API using a URL that is **baked at build time**. If that URL is not set when the image is built, it defaults to `http://localhost:8000`, so the deployed UI keeps trying to reach localhost and fails.

**Fix:** Rebuild the frontend with the deployed API URL.

- **Notebookllm (frontend) service on Render:** Set **Environment** → **API_BASE_URL** = `https://sparksbm-agent.onrender.com` (or your actual NotebookLLM API URL). Then **Manual Deploy** so the image is rebuilt. Render turns env vars into Docker build args automatically.
- **SparksBM-Web (ISMS dashboard with chatbot):** Set **NOTEBOOKLLM_API_URL** = `https://sparksbm-agent.onrender.com` (no trailing slash). Redeploy so the build picks it up. If the widget still shows "not accessible", wait 1–2 min and open the chat again—the agent may be cold-starting; the widget retries the health check once after 4s.

The Dockerfiles accept these as build args. The chat widget normalizes the API base URL (no trailing slash) and retries the health check once to handle cold start.

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
