FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy/ proxy/
COPY .env.example .env.example

RUN mkdir -p logs

EXPOSE 3001

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3001", "--timeout", "300", "proxy.server:app"]
