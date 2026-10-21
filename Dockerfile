FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt && useradd --uid 10001 --create-home appuser
COPY pyproject.toml LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && mkdir -p /models /app/reports/experiment && chown -R appuser:appuser /app /models
USER appuser
ENV RECLAB_MODEL_PATH=/models/model.joblib
ENV RECLAB_PROJECT_ROOT=/app
EXPOSE 8011
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8011/ready')"
CMD ["uvicorn", "reclab.api:app", "--host", "0.0.0.0", "--port", "8011"]
