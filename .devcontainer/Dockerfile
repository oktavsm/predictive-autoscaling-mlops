FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Remove expired upstream yarn repository to ensure apt-get update and features build cleanly
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Install k6 load testing binary
RUN curl -fsSL https://github.com/grafana/k6/releases/download/v0.54.0/k6-v0.54.0-linux-amd64.tar.gz | tar -xz -C /tmp \
    && mv /tmp/k6-v0.54.0-linux-amd64/k6 /usr/local/bin/k6 \
    && chmod +x /usr/local/bin/k6 \
    && rm -rf /tmp/k6-*

# Install kubectl CLI
RUN curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl
