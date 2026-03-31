# Incident Intelligence Agent

Turn a wall of logs into a human story.

This project implements a single Google ADK agent that accepts raw incident logs and returns a postmortem-style incident report using Gemini. It is designed to satisfy the hackathon requirement of one clearly defined AI capability exposed over HTTP and deployed on Cloud Run.

## What It Does

Send the agent a raw log dump from one incident window. The response is a structured incident analysis with:

- A plain-English incident summary
- A chronological timeline
- Trigger vs root cause analysis with confidence
- Blast radius analysis
- A 5 Whys chain
- A postmortem-ready summary paragraph
- Prioritized action items

## Project Structure

```text
cohort1academy/
|-- incident_intelligence/
|   |-- __init__.py
|   |-- agent.py
|   `-- tools.py
|-- .env.example
|-- .gitignore
|-- Dockerfile
|-- README.md
`-- requirements.txt
```

## Local Setup

### Prerequisites

- Python 3.11+
- A Gemini API key for local development

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure

Create `.env` from `.env.example` and set:

```env
GOOGLE_API_KEY=your_api_key_here
GOOGLE_CLOUD_PROJECT=primeval-camera-491818-h0
GOOGLE_CLOUD_LOCATION=us-central1
```

For local development, `GOOGLE_API_KEY` is the important variable. For Cloud Run deployment in GCP, the container is configured to use Vertex AI credentials from the runtime service account.

## Run Locally

### Web UI

```powershell
adk web
```

### HTTP API

```powershell
adk api_server --host 0.0.0.0 --port 8000 .
```

Useful endpoints include:

- `GET /health`
- `GET /list-apps`
- `POST /run`

## Deploy to Cloud Run

This repository includes a Dockerfile that runs the ADK API server on port `8080`, which matches Cloud Run expectations.

### GCP Prerequisites

- Project: `primeval-camera-491818-h0`
- Region: `us-central1`
- Cloud Run, Cloud Build, Artifact Registry, and Vertex AI APIs enabled
- A runtime service account with permission to call Vertex AI
- Build/deploy identities with permission to build images and deploy Cloud Run services

### Deploy

```powershell
gcloud builds submit --tag us-central1-docker.pkg.dev/primeval-camera-491818-h0/cloud-run-source-deploy/incident-intelligence
gcloud run deploy incident-intelligence `
  --image us-central1-docker.pkg.dev/primeval-camera-491818-h0/cloud-run-source-deploy/incident-intelligence `
  --region us-central1 `
  --project primeval-camera-491818-h0 `
  --allow-unauthenticated
```

If you prefer `adk deploy cloud_run`, make sure the Cloud Build and Compute Engine service accounts in this project have storage and build access first. Failures could be related to was an IAM issues.

## Example Input

```text
2024-03-15T14:32:01Z pod/auth-service-7d4b8c ERROR Connection refused to postgres-primary:5432
2024-03-15T14:32:05Z pod/auth-service-7d4b8c ERROR Pool exhausted: 0/20 connections available
2024-03-15T14:32:12Z pod/gateway-nginx WARN upstream timeout (110s) reading response from auth-service
2024-03-15T14:32:18Z pod/user-service-3a9f ERROR 503 from auth-service/v1/validate-token
2024-03-15T14:32:22Z pod/order-service-8b2e ERROR 503 from auth-service/v1/validate-token
2024-03-15T14:32:41Z alertmanager FIRING: AuthServiceDown severity=critical
2024-03-15T14:33:15Z pod/auth-service-7d4b8c INFO Restarting after OOMKilled (exit code 137)
2024-03-15T14:33:44Z pod/auth-service-7d4b8c INFO Connection established to postgres-primary:5432
2024-03-15T14:33:52Z pod/auth-service-7d4b8c INFO Pool initialized: 20/20 connections available
2024-03-15T14:34:01Z pod/gateway-nginx INFO upstream recovered: auth-service responding 200
```

## Submission Fit

This project matches the hackathon brief:

- One AI agent implemented with ADK
- Gemini used for inference
- One clearly defined task: incident-log analysis into a narrative report
- Callable over HTTP through the ADK API server
- Deployable to Cloud Run through the included container setup
