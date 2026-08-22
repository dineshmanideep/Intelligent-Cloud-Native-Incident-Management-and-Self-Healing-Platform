FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY incident_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY incident_service /app/incident_service

EXPOSE 8080
CMD ["uvicorn", "incident_service.app:app", "--host", "0.0.0.0", "--port", "8080"]

