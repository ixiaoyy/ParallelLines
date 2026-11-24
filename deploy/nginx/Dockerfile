FROM nginx:1.27-alpine

RUN apk add --no-cache openssl flock

COPY deploy/nginx/start-nginx.sh /usr/local/bin/start-nginx.sh
RUN chmod +x /usr/local/bin/start-nginx.sh

CMD ["/usr/local/bin/start-nginx.sh"]
