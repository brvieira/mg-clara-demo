FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Vite bakes VITE_* vars into the bundle at build time -- these must resolve
# to URLs reachable from the browser, not from inside the compose network, so
# they default to the same localhost ports the other services publish
# (see webapp/.env.example).
ARG VITE_API_BASE_URL=http://localhost:8080
ARG VITE_CUSTOMER_API_BASE_URL=http://localhost:8090
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_CUSTOMER_API_BASE_URL=$VITE_CUSTOMER_API_BASE_URL

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
