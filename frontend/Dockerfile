# CareQueue UI image. Multi-stage: Node builds and tests the React app, then an
# unprivileged nginx serves the static files. No Node, npm or sources ship.

# ---------- stage 1: build ----------
FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm test -- --run && npm run build

# ---------- stage 2: runtime ----------
# nginx-unprivileged runs as UID 101 and listens on 8080 (no root, no port 80).
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24@sha256:782bb89768cc87b7f95c18b95baa1af250e5d451f26794f59363540161147c01

LABEL org.opencontainers.image.source="https://github.com/rudhar07/carequeue-clinic" \
      org.opencontainers.image.title="carequeue-frontend" \
      org.opencontainers.image.description="CareQueue clinic UI (React + nginx)"

# Pick up Alpine security fixes published after the base image was built.
USER root
RUN apk upgrade --no-cache

# Default upstream for Docker Compose; Helm overrides it with the Service name.
ENV BACKEND_URL=http://backend:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

USER 101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
