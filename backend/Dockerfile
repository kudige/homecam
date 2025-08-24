FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends     ffmpeg     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY backend/start.sh /start.sh
RUN chmod +x /start.sh

# Media and DB volumes
VOLUME [ "/media", "/data" ]
ENV MEDIA="/media"

EXPOSE 8000
CMD ["/start.sh"]
