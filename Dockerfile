FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .
COPY inference.py .
COPY openenv.yaml .
COPY README.md .

# Expose port for HF Spaces
EXPOSE 7860

# Start server
CMD ["python", "app.py"]
