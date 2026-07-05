# Sirve el build de producción ya generado localmente (npm run build -> dist/).
# Se evita compilar dentro de Docker por la red lenta del entorno.
# Para regenerar: cd app/frontend && npm run build
FROM nginx:1.27-alpine
COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
