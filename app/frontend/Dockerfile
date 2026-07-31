# Build multi-stage: compila el frontend dentro de la imagen.
# Antes se copiaba el dist/ generado a mano en local, pero dist/ está en
# .gitignore, así que un clone limpio (Dokploy, CI) no lo tiene y el COPY
# fallaba. Compilar aquí hace el deploy reproducible desde git.
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
