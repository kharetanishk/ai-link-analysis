# Deployment

The app ships as **one Docker image**: the UI is built in the first stage and served by FastAPI in the second. Any host that runs Docker can run it.

---

## Option 1: Ubuntu server with nginx (how production runs)

Production: **Cloudflare (DNS + proxy) → nginx (HTTPS via Let's Encrypt) → Docker container on `127.0.0.1`**.

### Requirements

- Ubuntu 22.04+ with Docker + Docker Compose, nginx and certbot (`apt install docker.io docker-compose-v2 nginx certbot python3-certbot-nginx`)
- A domain or subdomain with an **A record** pointing to the server. With Cloudflare, keep the record **proxied** (orange cloud).

### First deploy

```bash
sudo git clone https://github.com/kharetanishk/ai-link-analysis.git /opt/ai-link-analysis
cd /opt/ai-link-analysis
sudo cp .env.example .env
sudo nano .env                     # paste GEMINI_API_KEY=...
sudo DOMAIN=link-analysis.example.com HOST_PORT=4200 bash deploy/deploy.sh
```

The script does five things:

1. Builds the image. If an old container exists, it keeps serving during the build.
2. Swaps the container, waiting for `/health` to report OK.
3. Renders `deploy/nginx.conf` for your domain, including Cloudflare's current IP ranges, so visitor IPs are correct for rate limiting.
4. Obtains or reinstalls the Let's Encrypt certificate and forces HTTPS.
5. Validates nginx and **rolls back automatically** if the configuration is invalid, so other sites on the server are never affected.

### Redeploy after code changes

```bash
cd /opt/ai-link-analysis && sudo git pull && sudo DOMAIN=link-analysis.example.com bash deploy/deploy.sh
```

### Operations

| Task | Command |
|---|---|
| Status / health | `docker ps --filter name=ai-link-analysis` · `curl -s 127.0.0.1:4200/health` |
| Logs | `docker logs -f --tail=100 ai-link-analysis` |
| Restart | `docker compose restart` (in `/opt/ai-link-analysis`) |
| Stop | `docker compose down` |
| Change settings | Edit `.env`, then `docker compose up -d --force-recreate` |

---

## Option 2: Local machine with Docker

```bash
cp .env.example .env      # add GEMINI_API_KEY
docker compose up -d --build
open http://localhost:4000
```

---

## Option 3: Managed container hosts (Render, Railway, Fly.io)

Point the service at this repository's `Dockerfile` and set:

| Setting | Value |
|---|---|
| Port | `4000` |
| Environment | `GEMINI_API_KEY` (as a secret), plus any optional variables from `.env.example` |
| Health check path | `/health` |
| Request timeout | ≥ 120 seconds |

These platforms terminate HTTPS themselves; nginx is not needed.

---

## Runtime hardening (already configured in `docker-compose.yml`)

- Runs as an unprivileged user (`uid 10001`)
- Read-only root filesystem; only `/tmp` is writable (tmpfs)
- All Linux capabilities dropped, `no-new-privileges`
- 512 MB memory and 1 CPU limit
- Port published on `127.0.0.1` only (reachable through the reverse proxy)
- Log rotation (3 × 10 MB)
- Docker health check on `/health`
