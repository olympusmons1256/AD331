FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 HF_HOME=/data/huggingface CHROMA_DIR=/data/chroma
WORKDIR /app

# Prefer the CPU wheels over the much larger default Linux CUDA distribution.
RUN pip install 'torch>=2.2,<3' --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY src ./src
COPY docs ./docs
RUN pip install . && mkdir -p /data/chroma /data/huggingface

EXPOSE 8501
CMD ["streamlit", "run", "src/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]