FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3
WORKDIR /app
COPY server.py /app/server.py
COPY static /app/static
CMD ["python3", "-u", "/app/server.py"]
