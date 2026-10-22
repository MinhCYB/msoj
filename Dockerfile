# syntax=docker/dockerfile:1.7
FROM node:20.19.1-bookworm-slim@sha256:83e53269616ca1b22cf7533e5db4e2f1a0c24a8e818b21691d6d4a69ec9e2c6d AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY make_style.sh ./make_style.sh
COPY scripts ./scripts
COPY resources ./resources
RUN ./make_style.sh

FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS python-build
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config git default-libmysqlclient-dev gettext libxml2-dev libxslt1-dev \
    libjpeg62-turbo-dev zlib1g-dev libffi-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY docker/requirements.lock docker/requirements-vcs.txt /tmp/
RUN python -m pip install --upgrade pip==25.1.1 setuptools==80.9.0 wheel==0.45.1 \
    && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
    && python -m pip install --no-deps -r /tmp/requirements-vcs.txt \
    && python -m pip check
COPY . .
COPY docker/settings.py /app/dmoj/local_settings.py
COPY --from=assets /app/resources /app/resources
ENV DJANGO_SETTINGS_MODULE=dmoj.settings MSOJ_BUILD=1
RUN python manage.py compilemessages --ignore='node_modules/*' \
    && python manage.py collectstatic --noinput --clear \
    && python manage.py compilejsi18n -o /app/static-build/jsi18n

FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS app
ARG APP_UID=1000
ARG APP_GID=1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=dmoj.settings STATIC_ROOT=/app/static-build PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 libxml2 libxslt1.1 libjpeg62-turbo zlib1g libffi8 libfreetype6 libpng16-16 libgomp1 curl ca-certificates \
&& case "$(dpkg --print-architecture)" in \
     amd64) pandoc_arch=amd64; pandoc_sha=ab0ac0aa1c3f9b23243d14e43023e06cbce51a52420aba17d27bd0d9c28f73ac ;; \
     arm64) pandoc_arch=arm64; pandoc_sha=0ec96f3af8b0618552d4fea8f0c90bb58e35e85675feeb04b3bcb31edafcdf87 ;; \
     *) echo "Unsupported Pandoc architecture" >&2; exit 1 ;; esac \
&& curl -fsSL "https://github.com/jgm/pandoc/releases/download/3.1.11.1/pandoc-3.1.11.1-1-${pandoc_arch}.deb" -o /tmp/pandoc.deb \
&& echo "${pandoc_sha}  /tmp/pandoc.deb" | sha256sum -c - \
    && apt-get install -y --no-install-recommends /tmp/pandoc.deb \
    && rm -f /tmp/pandoc.deb && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=python-build /usr/local /usr/local
COPY --from=python-build /app /app
COPY docker/uwsgi.ini /app/docker/uwsgi.ini
RUN mkdir -p /data/media /data/problems /app/static-build \
    && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["uwsgi", "--ini", "/app/docker/uwsgi.ini"]

FROM node:20.19.1-bookworm-slim@sha256:83e53269616ca1b22cf7533e5db4e2f1a0c24a8e818b21691d6d4a69ec9e2c6d AS events
ENV NODE_ENV=production
WORKDIR /app/websocket
COPY package.json /app/package.json
COPY package-lock.json /app/package-lock.json
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund --prefix /app
COPY websocket/daemon.js websocket/queue.js websocket/types.d.ts ./
COPY docker/events-config.js ./config.js
EXPOSE 9995 9996 9997
CMD ["node", "/app/websocket/daemon.js"]

FROM nginx:1.28.0-alpine@sha256:30f1c0d78e0ad60901648be663a710bdadf19e4c10ac6782c235200619158284 AS proxy
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=app /app/static-build /app/static-build
EXPOSE 80 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
