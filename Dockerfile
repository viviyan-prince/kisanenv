FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi==0.111.0 uvicorn==0.29.0 pydantic==2.7.1 requests==2.31.0 openai==1.30.1

# Copy application
COPY server/ ./server/
COPY inference.py .
COPY openenv.yaml .
COPY README.md .
COPY pyproject.toml .

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
