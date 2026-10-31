FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY corpus ./corpus
COPY data ./data

RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

EXPOSE 8501
CMD ["streamlit", "run", "src/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
