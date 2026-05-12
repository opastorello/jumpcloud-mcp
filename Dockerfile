FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

RUN mkdir -p logs

EXPOSE 8000

CMD ["uvicorn", "jumpcloud_mcp.main:app", "--host", "0.0.0.0", "--port", "8000"]
