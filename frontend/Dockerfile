# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .

# VITE_API_BASE=/api makes all API calls go through the Nginx proxy
# so the browser talks to a single origin (no CORS, no hardcoded host).
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# openssl: cert generation; curl: public-IP auto-detection via EC2 IMDS
RUN apk add --no-cache openssl curl

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY tls-entrypoint.sh /tls-entrypoint.sh
RUN chmod +x /tls-entrypoint.sh

EXPOSE 80 443
ENTRYPOINT ["/tls-entrypoint.sh"]
