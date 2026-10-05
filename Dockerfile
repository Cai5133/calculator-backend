FROM python:3.12-slim
WORKDIR /app
COPY . /app/backend/
ENV CALCULATOR_HOST=0.0.0.0
ENV CALCULATOR_DB_PATH=/app/data/calculator.sqlite3
EXPOSE 8000
CMD ["python", "-m", "backend.server"]
