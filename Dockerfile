FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ./app /app

# Expose port
EXPOSE 8080 

# Run application
CMD ["python", "app.py"]