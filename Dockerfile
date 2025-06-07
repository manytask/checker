ARG PYTHON_VERSION=3.12

# Stage 1: Python dependencies
FROM python:${PYTHON_VERSION}-slim AS builder

# Install build tools for cpp and rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gawk \
    build-essential \
    libssl-dev \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# Build firejail from source
RUN git clone --depth 1 --branch 0.9.72 https://github.com/netblue30/firejail.git
WORKDIR /firejail
RUN ./configure && make && make install-strip

# Install python dependencies
WORKDIR /usr/src/app
COPY . .
RUN python -m venv /opt/checker-venv
RUN /opt/checker-venv/bin/python -m pip install --no-cache-dir --require-virtualenv . \
    && find /opt/checker-venv -type d -name '__pycache__' -exec rm -r {} + \
    && find /opt/checker-venv -name '*.py[co]' -delete


# Stage 2: Runtime stage
FROM python:${PYTHON_VERSION}-slim

WORKDIR /usr/src/app

# Install additional tools
RUN apt-get update  \
    && apt-get install -y --no-install-recommends \
        git

# Copy firejail and python environment
COPY --from=builder /usr/local/bin/firejail /usr/local/bin/firejail
COPY --from=builder /opt/checker-venv /opt/checker-venv

# Create symlink for checker
RUN ln -s /opt/checker-venv/bin/checker /usr/local/bin/checker

ENTRYPOINT [ "checker" ]
CMD [ "--help" ]
