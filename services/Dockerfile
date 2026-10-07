FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY services/requirements.txt ./requirements.txt
RUN uv pip install --system -r requirements.txt

COPY services/ .
COPY data/ /app/data/
COPY docs/company-knowledge-base/ /app/docs/company-knowledge-base/

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin trackflow \
    && mkdir -p /app/backups \
    && chown -R trackflow:trackflow /app
USER trackflow

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]