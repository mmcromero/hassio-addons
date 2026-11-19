FROM alpine:3.20
# Git is needed for read-only preflight and isolated export preparation.
# No Node, cloud SDK, GitHub Actions, publishing daemon or implicit credentials.
RUN apk add --no-cache python3 bash jq git
WORKDIR /app
COPY server.py autonomous_dev.py rc_fastlane.py run.sh /app/
COPY projects/ /app/projects/
RUN chmod 0755 /app/run.sh
EXPOSE 9876
CMD ["/bin/bash", "/app/run.sh"]
