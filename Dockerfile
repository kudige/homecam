# syntax=docker/dockerfile:1

# Frontend build stage
FROM node:18 AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Final image with backend and nginx
FROM python:3.11-slim

# install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nginx gettext-base \
    && rm -rf /var/lib/apt/lists/*

# backend setup
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/start.sh /start.sh
RUN chmod +x /start.sh

# copy frontend build and nginx config template
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html
COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf.template
COPY deploy/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# volumes for media, db, recordings
VOLUME ["/media", "/data", "/recordings"]
ENV MEDIA_ROOT=/media \
    DB_PATH=/data/homecam.db \
    RECORDINGS_ROOT=/recordings \
    SERVICE=all

EXPOSE 8090 8091
ENTRYPOINT ["/docker-entrypoint.sh"]
