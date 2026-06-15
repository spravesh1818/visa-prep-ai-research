# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build — Vite + React production bundle
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty = same-origin API calls via nginx reverse proxy (/config, /voice, …)
ARG VITE_API_BASE=
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

# ---------------------------------------------------------------------------
# Serve — nginx serves the SPA (internal network only; public nginx terminates SSL)
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
