ARG PYTHON_VERSION=3.12

# Stage 1: Python dependencies
FROM python:${PYTHON_VERSION}-alpine as builder

# Install build tools for cpp and rust
RUN apk update && apk add --no-cache \
    git \
    gawk \
    linux-headers \
    build-base \
    cargo \
    rust \
    && rm -rf /var/cache/apk/*

# Build firejail from source
RUN git clone --depth 1 --branch 0.9.72 https://github.com/netblue30/firejail.git
WORKDIR /firejail
RUN ./configure && make && make install-strip && firejail --version

# Install python dependencies
WORKDIR /usr/src/app

# Copy source code
COPY pyproject.toml VERSION Makefile setup.py README.md ./
COPY checker ./checker

# Install python dependencies and checker
RUN python -m venv /opt/checker-venv
RUN /opt/checker-venv/bin/python -m pip install --no-cache-dir --require-virtualenv . && \
    find /opt/checker-venv -type d -name '__pycache__' -exec rm -r {} + && \
    find /opt/checker-venv -type d -name 'tests' -exec rm -rf {} + && \
    find /opt/checker-venv -name '*.pyc' -delete && \
    find /opt/checker-venv -name '*.pyo' -delete && \
    rm -rf /tmp/*


# Stage 2: Runtime stage
FROM python:${PYTHON_VERSION}-alpine

WORKDIR /usr/src/app

# Install additional tools
RUN apk update  \
    && apk add --no-cache \
        git

# Copy firejail
COPY --from=builder /usr/local/bin/firejail /usr/local/bin/firejail

# Copy python dependencies and checker
COPY --from=builder /opt/checker-venv /opt/checker-venv

ENTRYPOINT [ "/opt/checker-venv/bin/python", "-m", "checker" ]
CMD [ "--help" ]
