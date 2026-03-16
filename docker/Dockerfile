FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

ENTRYPOINT ["autocollector"]
CMD ["scan"]
