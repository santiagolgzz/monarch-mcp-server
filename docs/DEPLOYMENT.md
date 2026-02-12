# Deploying Monarch Money MCP Server Online

This guide explains how to host the Monarch Money MCP server online so you can use it with the **Claude mobile app** or other remote MCP clients.

## Overview

The server uses **SSE (Server-Sent Events)** transport, which is the standard for remote MCP servers. It includes:
- Single-user token authentication by default (`MCP_AUTH_MODE=token`)
- Optional GitHub OAuth mode for advanced/multi-user setups (`MCP_AUTH_MODE=oauth`)
- Health check endpoint for monitoring
- Docker support for easy deployment

## Prerequisites

1. A Monarch Money account
2. A server/cloud platform to host the MCP server (see options below)
3. Your Monarch Money authentication token

## Step 1: Get Your Monarch Money Token

Before deploying, you need to authenticate with Monarch Money locally:

```bash
# Clone and setup locally first
git clone https://github.com/santiagolgzz/monarch-mcp-server.git
cd monarch-mcp-server
pip install -e .

# Run the login setup
python login_setup.py
```

After logging in successfully, extract your token:

```bash
# The token is saved in your keyring or session file
# You can extract it with:
python -c "from monarch_mcp_server.secure_session import secure_session; print(secure_session.load_token())"
```

Save this token - you'll need it for deployment.

## Step 2 (Optional): Create a GitHub OAuth App

You only need this if you choose `MCP_AUTH_MODE=oauth`.

If you're in the common single-user setup, skip this step and use `MCP_AUTH_MODE=token` with `MCP_AUTH_TOKEN`.

For OAuth mode, create an OAuth App:

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: Monarch MCP Server (or any name)
   - **Homepage URL**: Your deployment URL (e.g., `https://your-app.railway.app`)
   - **Authorization callback URL**: `https://your-deployment-url/auth/callback`
4. Click "Register application"
5. Copy the **Client ID**
6. Generate and copy a **Client Secret**

Save both values - you'll need them for deployment.

## Step 3: Deploy the Server

### Option A: GitHub Actions + Cloud Run (Recommended - Automated)

This repository includes a CD pipeline that automatically deploys to Google Cloud Run on every push to `main`. The workflow is designed to be **fork-friendly** — it only runs if you configure the required secrets.

**One-time GCP Setup:**

```bash
# 1. Create Artifact Registry repository
gcloud artifacts repositories create monarch-mcp \
  --repository-format=docker \
  --location=us-central1 \
  --description="Monarch MCP Server images"

# 2. Create service account for GitHub Actions
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

# 3. Grant permissions
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" --role="roles/iam.serviceAccountUser"

# 4. Create and download key
gcloud iam service-accounts keys create ~/github-actions-key.json \
  --iam-account=$SA_EMAIL
cat ~/github-actions-key.json  # Copy this for GitHub Secrets
```

**GitHub Repository Configuration:**

Go to Settings → Secrets and variables → Actions:

*Variables* (not secret, but project-specific):
- `GCP_PROJECT_ID` = your GCP project ID
- `GCP_REGION` = `us-central1` (optional)
- `CLOUD_RUN_URL` = `https://monarch-mcp-server-xxxxx-uc.a.run.app` (set after first deploy)

*Secrets* (encrypted):
- `GCP_SA_KEY` = paste the entire JSON key file content
- `MCP_AUTH_TOKEN` = long random secret used by your MCP client in Bearer auth
- `MONARCH_TOKEN` = your Monarch Money token

Optional only for advanced oauth mode:
- `GITHUB_CLIENT_SECRET` = GitHub OAuth App secret
- `GITHUB_CLIENT_ID` = GitHub OAuth App client ID
- `OAUTH_REDIS_URL` = Redis URL used to persist OAuth state
- `OAUTH_JWT_SIGNING_KEY` = stable JWT signing key for OAuth tokens

Note: the default CD workflow deploys in token mode (`MCP_AUTH_MODE=token`) and validates real MCP calls on `/mcp`.

**First Deployment:**
1. Configure the variables/secrets above (leave `CLOUD_RUN_URL` empty initially)
2. Push to `main` or manually trigger the workflow
3. Get the Cloud Run URL from the deployment output
4. Set `CLOUD_RUN_URL` variable with the actual URL
5. If using OAuth mode, update callback URL to: `https://your-cloud-run-url/auth/callback`
6. Re-run the workflow if BASE_URL or OAuth settings changed

After setup, every merge to `main` automatically deploys.
Deploy is only marked healthy if:
1. `/health` is reachable
2. `/ready` passes readiness checks
3. a real authenticated MCP flow succeeds on `/mcp` (`initialize -> tools/list -> tools/call`)

### Option B: Railway (Easiest Manual Setup)

[Railway](https://railway.app) offers simple deployment with free tier:

1. Fork this repository on GitHub
2. Connect Railway to your GitHub account
3. Create new project → Deploy from GitHub repo
4. Add environment variables:
   - `MCP_AUTH_MODE` = `token` (recommended)
   - `MCP_AUTH_TOKEN` = long random secret
   - `MONARCH_TOKEN` = your Monarch Money token
   - (`GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` only if using oauth mode)
5. Railway will automatically deploy and give you a URL
6. If using oauth mode, update callback URL to: `https://your-app.railway.app/auth/callback`

### Option C: Render

[Render](https://render.com) offers free tier with easy setup:

1. Create a new Web Service
2. Connect your GitHub repository
3. Configure:
   - **Build Command**: `pip install .`
   - **Start Command**: `monarch-mcp-http`
4. Add environment variables (same as above)

### Option D: Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch

# Set secrets
fly secrets set GITHUB_CLIENT_ID="your-github-client-id"
fly secrets set GITHUB_CLIENT_SECRET="your-github-client-secret"
fly secrets set MCP_AUTH_MODE="token"
fly secrets set MCP_AUTH_TOKEN="your-long-random-secret"
fly secrets set MONARCH_TOKEN="your-monarch-token"

# Deploy
fly deploy
```

### Option E: Docker (Self-hosted)

```bash
# Clone the repository
git clone https://github.com/santiagolgzz/monarch-mcp-server.git
cd monarch-mcp-server

# Copy and edit environment file
cp .env.example .env
# Edit .env with your values

# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t monarch-mcp-server .
docker run -d -p 8000:8000 \
  -e GITHUB_CLIENT_ID="your-github-client-id" \
  -e GITHUB_CLIENT_SECRET="your-github-client-secret" \
  -e MCP_AUTH_MODE="token" \
  -e MCP_AUTH_TOKEN="your-long-random-secret" \
  -e MONARCH_TOKEN="your-monarch-token" \
  -e BASE_URL="https://your-domain.com" \
  monarch-mcp-server
```

### Option F: Google Cloud Run

Cloud Run requires explicit `BASE_URL` configuration since it doesn't provide auto-discoverable URLs:

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/monarch-mcp-server

# Deploy to Cloud Run
gcloud run deploy monarch-mcp-server \
  --image gcr.io/PROJECT_ID/monarch-mcp-server \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GITHUB_CLIENT_ID=your-github-client-id" \
  --set-env-vars "GITHUB_CLIENT_SECRET=your-github-client-secret" \
  --set-env-vars "MCP_AUTH_MODE=token" \
  --set-env-vars "MCP_AUTH_TOKEN=your-long-random-secret" \
  --set-env-vars "MONARCH_TOKEN=your-monarch-token" \
  --set-env-vars "BASE_URL=https://monarch-mcp-server-HASH-uc.a.run.app"
```

**Important**: After deployment, Cloud Run will give you a URL (e.g., `https://monarch-mcp-server-abc123-uc.a.run.app`). You must:
1. Update `BASE_URL` with the actual URL
2. If using oauth mode, update callback URL to: `https://your-cloud-run-url/auth/callback`
3. Redeploy with the correct `BASE_URL`

### Option G: VPS (DigitalOcean, AWS EC2, etc.)

```bash
# On your VPS
git clone https://github.com/santiagolgzz/monarch-mcp-server.git
cd monarch-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install
pip install .

# Set environment variables
export GITHUB_CLIENT_ID="your-github-client-id"
export GITHUB_CLIENT_SECRET="your-github-client-secret"
export MCP_AUTH_MODE="token"
export MCP_AUTH_TOKEN="your-long-random-secret"
export MONARCH_TOKEN="your-monarch-token"
export BASE_URL="https://your-domain.com"

# Run with systemd (recommended) or directly
monarch-mcp-http
```

For production, create a systemd service:

```ini
# /etc/systemd/system/monarch-mcp.service
[Unit]
Description=Monarch Money MCP Server
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/monarch-mcp-server
Environment="GITHUB_CLIENT_ID=your-github-client-id"
Environment="GITHUB_CLIENT_SECRET=your-github-client-secret"
Environment="MCP_AUTH_MODE=token"
Environment="MCP_AUTH_TOKEN=your-long-random-secret"
Environment="MONARCH_TOKEN=your-monarch-token"
Environment="BASE_URL=https://your-domain.com"
ExecStart=/path/to/venv/bin/monarch-mcp-http
Restart=always

[Install]
WantedBy=multi-user.target
```

## Step 4: Configure Claude Mobile App

Once your server is deployed and running:

1. Open the Claude mobile app
2. Go to Settings → MCP Servers (or similar)
3. Add a new MCP server:
   - **URL**: `https://your-server-url.com/mcp`
   - **Auth (recommended)**: Bearer token using `MCP_AUTH_TOKEN`
   - **Auth (optional)**: GitHub OAuth (only if `MCP_AUTH_MODE=oauth`)

The server URL format depends on your deployment:
- Railway: `https://your-app.up.railway.app/mcp`
- Render: `https://your-app.onrender.com/mcp`
- Fly.io: `https://your-app.fly.dev/mcp`
- Self-hosted: `https://your-domain.com/mcp`

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Server info and available endpoints |
| `/health` | Liveness check (process up; no auth/path validation) |
| `/ready` | Readiness check (auth + MCP wiring validation) |
| `/mcp` | MCP endpoint (requires Bearer token or OAuth, based on mode) |
| `/.well-known/oauth-authorization-server` | OAuth discovery endpoint (oauth mode only) |

## Security Considerations

1. **Always use HTTPS** in production (most cloud platforms provide this automatically)
2. **Keep your API key secret** - don't commit it to git
3. **Rotate tokens periodically** - Monarch tokens can expire
4. **Monitor access** - Check logs for unauthorized access attempts

## Troubleshooting

### Server won't start
- For token mode: check `MCP_AUTH_MODE=token` and `MCP_AUTH_TOKEN` are set
- For oauth mode: check `MCP_AUTH_MODE=oauth`, `GITHUB_CLIENT_ID`, and `GITHUB_CLIENT_SECRET`
- Verify `MONARCH_TOKEN` is valid (try running locally first)

### Can't connect from Claude app
- Ensure you're using the `/mcp` endpoint (not `/sse`)
- If token mode: verify your client sends `Authorization: Bearer <MCP_AUTH_TOKEN>`
- If oauth mode: verify GitHub OAuth callback URL matches your deployment URL
- Verify the server is accessible (try `/health` endpoint in browser)
- Verify auth/MCP readiness (check `/ready`; must return `status=ready`)

### Authentication errors with Monarch
- Your token may have expired
- Run `python login_setup.py` again locally and get a fresh token

### Rate limiting
- The server inherits safety limits from the local version
- Check `/ready` for readiness status and `/health` for liveness

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_AUTH_MODE` | No | Auth mode: `token` (default) or `oauth` |
| `MCP_AUTH_TOKEN` | Yes* | Shared bearer token for `token` mode |
| `GITHUB_CLIENT_ID` | Yes** | GitHub OAuth App Client ID (`oauth` mode only) |
| `GITHUB_CLIENT_SECRET` | Yes** | GitHub OAuth App Client Secret (`oauth` mode only) |
| `MCP_OAUTH_REDIS_URL` | Yes** | Shared Redis URL for durable OAuth state |
| `MCP_OAUTH_JWT_SIGNING_KEY` | Yes** | Stable token signing key for OAuth |
| `MCP_ENABLE_CI_SMOKE` | No | Enables `/mcp-smoke` endpoint for CI (default: false) |
| `MCP_CI_SMOKE_TOKEN` | Yes*** | Bearer token required for `/mcp-smoke` |
| `MONARCH_TOKEN` | Yes* | Monarch Money authentication token |
| `MONARCH_EMAIL` | No | Email for auto-login (alternative to token) |
| `MONARCH_PASSWORD` | No | Password for auto-login (alternative to token) |
| `BASE_URL` | No** | Server's public URL (auto-detected on Railway) |
| `HOST` | No | Server host (default: 0.0.0.0) |
| `PORT` | No | Server port (default: 8000) |
| `DEBUG` | No | Enable debug logging (default: false) |

*`MCP_AUTH_TOKEN` is required when `MCP_AUTH_MODE=token`. Also, either `MONARCH_TOKEN` or `MONARCH_EMAIL`+`MONARCH_PASSWORD` is required.
**Required only when `MCP_AUTH_MODE=oauth`.
***Required when `MCP_ENABLE_CI_SMOKE=true`.

**`BASE_URL` is auto-detected on Railway. Required for other platforms (Render, Fly.io, VPS, Cloud Run).
