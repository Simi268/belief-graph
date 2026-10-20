FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY examples/ ./examples/
COPY experiments/ ./experiments/
COPY data/ ./data/
COPY tests/ ./tests/
COPY *.py ./
COPY README.md .

RUN mkdir -p /app/data /app/artifacts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]