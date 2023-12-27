ARG PYTHON_VERSION=3.12

# Stage 1: Build stage
FROM python:${PYTHON_VERSION}-alpine as builder

WORKDIR /usr/src/app

COPY pyproject.toml VERSION Makefile setup.py README.md ./
COPY checker ./checker

RUN python -m venv /opt/checker-venv
RUN /opt/checker-venv/bin/python -m pip install --no-cache-dir --require-virtualenv .
RUN find /opt/checker-venv -type d -name '__pycache__' -exec rm -r {} + && \
    find /opt/checker-venv -type d -name 'tests' -exec rm -rf {} + && \
    find /opt/checker-venv -name '*.pyc' -delete && \
    find /opt/checker-venv -name '*.pyo' -delete


# Stage 2: Runtime stage
FROM python:${PYTHON_VERSION}-alpine

WORKDIR /usr/src/app

COPY --from=builder /opt/checker-venv /opt/checker-venv

ENTRYPOINT [ "/opt/checker-venv/bin/python", "-m", "checker" ]
CMD [ "--help" ]
