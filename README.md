# Agent Deployer

A simple tool to deploy Python APIs (Flask, FastAPI, Django) to servers with systemd and Nginx configuration.

## Features

- Supports Flask, FastAPI, and Django applications
- Creates systemd service files for process management
- Sets up Nginx configuration with optional SSL via Certbot
- Supports frontend deployment with separate API and frontend routing
- Handles environment variables
- Simple command-line interface with detailed progress logs
- Clear information about how to access your deployed application

## Installation

```bash
pip install agent-deployer
```

## Usage

```bash
# Basic usage
agent-deploy \
  --project-path ~/repos/my-agent \
  --service-name myagent \
  --framework fastapi \
  --port 8000 \
  --venv-name venv

# Full example with all options
agent-deploy \
  --project-path ~/repos/my-agent \
  --service-name myagent \
  --framework fastapi \
  --workers 4 \
  --timeout 60 \
  --port 8002 \
  --venv-name venv \
  --domain agent.example.com \
  --enable-db \
  --env-file .env \
  --verbose

# Example with frontend deployment
agent-deploy \
  --project-path ~/repos/my-agent \
  --service-name myagent \
  --framework fastapi \
  --port 8002 \
  --venv-name venv \
  --domain agent.example.com \
  --frontend-path ~/repos/my-agent/frontend/build \
  --frontend-url-prefix / \
  --api-url-prefix /api
```

## Requirements

- Linux server with systemd
- Nginx installed (will be checked and can be installed automatically)
- Python 3.6+
- Sudo access for service installation
- Certbot for SSL certificates (will be checked and can be installed automatically)

The tool will automatically check for required system dependencies and offer to install them if they're missing.

## Options

| Option | Description |
|--------|-------------|
| `--project-path` | Path to the project directory (required) |
| `--service-name` | Name for the systemd service (required) |
| `--framework` | Python web framework: flask, fastapi, or django (required) |
| `--port` | Port to run the service on (required) |
| `--venv-name` | Name of virtual environment directory (required) |
| `--workers` | Number of worker processes (default: 2) |
| `--timeout` | Worker timeout in seconds (default: 120) |
| `--domain` | Domain name for Nginx configuration |
| `--enable-db` | Enable database connection |
| `--env-file` | Path to environment file |
| `--frontend-path` | Path to frontend build directory |
| `--frontend-url-prefix` | URL prefix for frontend (default: /) |
| `--api-url-prefix` | URL prefix for API endpoints (default: /api) |
| `--verbose` | Enable verbose output |

## License

MIT