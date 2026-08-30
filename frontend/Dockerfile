FROM nginx:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html
COPY operations.html /usr/share/nginx/html/operations.html
COPY diagnosis.html /usr/share/nginx/html/diagnosis.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
