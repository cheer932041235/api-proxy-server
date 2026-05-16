FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY index.html style.css script.js server.py ./
EXPOSE 8088
CMD ["python3", "-u", "server.py"]
