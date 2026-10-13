# ---- 1. Build the React app
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python app (Django API + compression engine)
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist \
    DOCFIT_STORAGE=/data/storage

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY --from=frontend /app/dist /app/frontend/dist
RUN SECRET_KEY=build-only DEBUG=0 python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 docfit && mkdir -p /data/storage && chown -R docfit /data
USER docfit
EXPOSE 8000

# gthread workers: slow uploads on mobile connections don't block other users.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn docfit.wsgi -b 0.0.0.0:8000 -k gthread -w 3 --threads 8 --timeout 600 --access-logfile -"]
