FROM python:3.10-slim AS base
ENV PYTHONUNBUFFERED=1

WORKDIR /app


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc \
      libpq-dev \
      python3-dev \
      curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./
RUN pip install --upgrade pip


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser


EXPOSE 5010
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:5010/health || exit 1


CMD ["python", "-u", "server.py"]
