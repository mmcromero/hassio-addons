FROM alpine:3.20
RUN apk add --no-cache python3 bash jq
WORKDIR /app
COPY server.py autonomous_dev.py run.sh /app/
RUN chmod 0755 /app/run.sh
EXPOSE 9876
CMD ["/bin/bash", "/app/run.sh"]
