FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOWNLOAD_ROOT=/srv/ytfetcher/downloads

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends ffmpeg nginx supervisor \ 
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app /srv/ytfetcher/downloads /var/log/ytfetcher /var/log/nginx /var/www/certbot

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ytfetcher ./ytfetcher
COPY main.py ./
COPY AGENTS.md ./
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
