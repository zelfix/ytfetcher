FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOWNLOAD_ROOT=/srv/ytfetcher/downloads

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends ffmpeg nginx supervisor \ 
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app /srv/ytfetcher/downloads /var/log/ytfetcher /var/log/nginx

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ytfetcher ./ytfetcher
COPY main.py ./
COPY AGENTS.md ./
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
