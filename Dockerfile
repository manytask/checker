ARG PYTHON_VERSION=3.12

# Stage 1: Build stage
FROM python:${PYTHON_VERSION}-alpine as builder

WORKDIR /usr/src/app

# Install build tools for cpp and rust
RUN apk add --no-cache --virtual .build-deps \ && \
    apk add --no-cache --virtual .build-deps gcc g++ make cmake musl-dev && \
    apk add --no-cache --virtual .build-deps rust cargo \
    && rm -rf /var/cache/apk/* \
    && rm -rf /tmp/*

# Copy source code
COPY pyproject.toml VERSION Makefile setup.py README.md ./
COPY checker ./checker

# Install python dependencies
RUN python -m venv /opt/checker-venv
RUN /opt/checker-venv/bin/python -m pip install --no-cache-dir --require-virtualenv .
RUN find /opt/checker-venv -type d -name '__pycache__' -exec rm -r {} + && \
    find /opt/checker-venv -type d -name 'tests' -exec rm -rf {} + && \
    find /opt/checker-venv -name '*.pyc' -delete && \
    find /opt/checker-venv -name '*.pyo' -delete && \
    rm -rf /tmp/*


# Stage 2: Runtime stage
FROM python:${PYTHON_VERSION}-alpine

WORKDIR /usr/src/app

COPY --from=builder /opt/checker-venv /opt/checker-venv

ENTRYPOINT [ "/opt/checker-venv/bin/python", "-m", "checker" ]
CMD [ "--help" ]
