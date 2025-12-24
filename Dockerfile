FROM python:3.11-slim

WORKDIR /app

RUN pip install flask

COPY app.py .

ENV PORT=8080

CMD ["python", "app.py"]
