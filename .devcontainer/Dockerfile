FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Remove expired upstream yarn repository to ensure apt-get update and features build cleanly
RUN rm -f /etc/apt/sources.list.d/yarn.list
