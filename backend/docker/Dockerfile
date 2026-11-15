# Reviewed multi-platform Python image; uv and dependencies are pinned separately.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

WORKDIR /backend

RUN python -m pip install --no-cache-dir uv==0.13.8

# Keep Linux dependencies outside the development source bind mount.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "if [ \"$DJANGO_MCP_ENABLED\" = \"1\" ]; then exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers; else exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --worker-class gthread --threads 4 --timeout 120; fi"]
