FROM docker.io/library/nginx:1.27-alpine
RUN apk add --no-cache openssl wget ca-certificates \
    && mkdir -p /etc/nginx/ssl
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY index.html style.css app.js enroll.html enroll.js /usr/share/nginx/html/
COPY assets /usr/share/nginx/html/assets/
COPY favicon.ico favicon-16.png favicon-32.png favicon-48.png apple-touch-icon.png /usr/share/nginx/html/
EXPOSE 80 443
CMD ["/docker-entrypoint.sh"]
