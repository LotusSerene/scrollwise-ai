FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}"]