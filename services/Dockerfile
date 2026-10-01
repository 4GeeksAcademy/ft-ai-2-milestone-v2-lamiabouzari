FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY services/requirements.txt ./requirements.txt
RUN uv pip install --system -r requirements.txt

COPY services/ .
COPY data/ /app/data/
COPY docs/company-knowledge-base/ /app/docs/company-knowledge-base/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]