# Deploying Monarch Money MCP Server Online

This guide explains how to host the Monarch Money MCP server online so you can use it with the **Claude mobile app** or other remote MCP clients.

## Overview

The server uses **SSE (Server-Sent Events)** transport, which is the standard for remote MCP servers. It includes:
- API key authentication for security
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

## Step 2: Generate an API Key

Generate a secure API key for authenticating requests:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save this key - you'll configure it on both the server and in the Claude app.

## Step 3: Deploy the Server

### Option A: Railway (Recommended - Easiest)

[Railway](https://railway.app) offers simple deployment with free tier:

1. Fork this repository on GitHub
2. Connect Railway to your GitHub account
3. Create new project → Deploy from GitHub repo
4. Add environment variables:
   - `MCP_API_KEY` = your generated API key
   - `MONARCH_TOKEN` = your Monarch Money token
5. Railway will automatically deploy and give you a URL

### Option B: Render

[Render](https://render.com) offers free tier with easy setup:

1. Create a new Web Service
2. Connect your GitHub repository
3. Configure:
   - **Build Command**: `pip install .`
   - **Start Command**: `monarch-mcp-http`
4. Add environment variables (same as above)

### Option C: Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch

# Set secrets
fly secrets set MCP_API_KEY="your-api-key"
fly secrets set MONARCH_TOKEN="your-monarch-token"

# Deploy
fly deploy
```

### Option D: Docker (Self-hosted)

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
  -e MCP_API_KEY="your-api-key" \
  -e MONARCH_TOKEN="your-monarch-token" \
  monarch-mcp-server
```

### Option E: VPS (DigitalOcean, AWS EC2, etc.)

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
export MCP_API_KEY="your-api-key"
export MONARCH_TOKEN="your-monarch-token"

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
Environment="MCP_API_KEY=your-api-key"
Environment="MONARCH_TOKEN=your-monarch-token"
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
   - **URL**: `https://your-server-url.com/sse`
   - **API Key**: Your `MCP_API_KEY` value

The server URL format depends on your deployment:
- Railway: `https://your-app.up.railway.app/sse`
- Render: `https://your-app.onrender.com/sse`
- Fly.io: `https://your-app.fly.dev/sse`
- Self-hosted: `https://your-domain.com/sse`

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Server info and available endpoints |
| `/health` | Health check (no auth required) |
| `/sse` | SSE endpoint for MCP protocol |
| `/messages/` | Message endpoint for MCP protocol |

## Security Considerations

1. **Always use HTTPS** in production (most cloud platforms provide this automatically)
2. **Keep your API key secret** - don't commit it to git
3. **Rotate tokens periodically** - Monarch tokens can expire
4. **Monitor access** - Check logs for unauthorized access attempts

## Troubleshooting

### Server won't start
- Check that `MCP_API_KEY` is set
- Verify `MONARCH_TOKEN` is valid (try running locally first)

### Can't connect from Claude app
- Ensure you're using the `/sse` endpoint
- Check that the API key matches
- Verify the server is accessible (try `/health` endpoint in browser)

### Authentication errors with Monarch
- Your token may have expired
- Run `python login_setup.py` again locally and get a fresh token

### Rate limiting
- The server inherits safety limits from the local version
- Check `/health` endpoint for current status

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_API_KEY` | Yes | API key for authenticating MCP requests |
| `MONARCH_TOKEN` | Yes* | Monarch Money authentication token |
| `MONARCH_EMAIL` | No | Email for auto-login (alternative to token) |
| `MONARCH_PASSWORD` | No | Password for auto-login (alternative to token) |
| `HOST` | No | Server host (default: 0.0.0.0) |
| `PORT` | No | Server port (default: 8000) |
| `DEBUG` | No | Enable debug logging (default: false) |

*Either `MONARCH_TOKEN` or `MONARCH_EMAIL`+`MONARCH_PASSWORD` is required.
