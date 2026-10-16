FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./
COPY .env.example ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
