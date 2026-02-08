# Stage 1: build Vite app (build context = repo root)
FROM node:22-alpine AS builder
WORKDIR /app

COPY mobile/package.json mobile/package-lock.json* ./
RUN npm ci
COPY mobile/ .

# Build-time env (VITE_API_BASE_URL set by docker-compose or build-arg)
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
