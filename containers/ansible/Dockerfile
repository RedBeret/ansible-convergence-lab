FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash ca-certificates make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /tmp/project/
COPY src /tmp/project/src
RUN pip install /tmp/project

ENTRYPOINT ["bash", "-lc"]
CMD ["make help"]

