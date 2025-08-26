# 1. Base Image
FROM python:3.11-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Set work directory
WORKDIR /app

# 4. Install dependencies
# Copy only requirements to leverage Docker cache
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    python -m spacy download fr_core_news_lg

# 5. Copy application code
COPY . .

# 6. Expose port and define command
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]