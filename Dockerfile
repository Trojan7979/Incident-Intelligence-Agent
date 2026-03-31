FROM python:3.11-slim

ARG GOOGLE_CLOUD_PROJECT=primeval-camera-491818-h0
ARG GOOGLE_CLOUD_LOCATION=us-central1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=1 \
    GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT} \
    GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}

WORKDIR /app

RUN adduser --disabled-password --gecos "" myuser

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install google-adk==1.28.0 -r requirements.txt

COPY --chown=myuser:myuser incident_intelligence/ /app/agents/incident_intelligence/

USER myuser

EXPOSE 8080

CMD ["sh", "-c", "adk api_server --host 0.0.0.0 --port ${PORT} --memory_service_uri=memory:// --session_service_uri=memory:// --artifact_service_uri=memory:// --auto_create_session /app/agents"]
