FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN mkdir -p /var/lib/cli-device-sim

COPY pyproject.toml README.md /tmp/project/
COPY src /tmp/project/src
RUN pip install /tmp/project

EXPOSE 8080

ENTRYPOINT ["simulator-server"]
