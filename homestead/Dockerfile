# The web interface is built with Node, then served by the Python server.
FROM node:24-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/homestead
COPY server/ ./
COPY --from=ui /ui/dist/ homestead_server/static/
RUN pip install . && rm -rf build ./*.egg-info
EXPOSE 8099
CMD ["homestead-server"]
