FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY deploy/nginx/start-nginx.sh /usr/local/bin/start-nginx.sh
RUN chmod +x /usr/local/bin/start-nginx.sh

CMD ["/usr/local/bin/start-nginx.sh"]
