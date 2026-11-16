# Base Image
FROM ubuntu:22.04

# Set non-interactive mode and include /usr/games in PATH (where cowsay and fortune reside)
ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/usr/games:${PATH}"

# Install dependencies and clean up apt cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fortune-mod \
        fortunes \
        cowsay \
        netcat-openbsd \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Set working directory
WORKDIR /app

# Copy application script and set ownership & permissions
COPY wisecow.sh /app/wisecow.sh
RUN chmod +x /app/wisecow.sh && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose Wisecow server port
EXPOSE 4499

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4499/ || exit 1

# Start the application
CMD ["/app/wisecow.sh"]
