ARG PATHWAY_SRC_IMAGE=pathwaycom/pathway:latest
FROM ${PATHWAY_SRC_IMAGE}

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY app.yaml .

# Create necessary directories
RUN mkdir -p /app/data /app/Cache

# Expose ports
# 8000 for FastAPI
# 8080 for Pathway RAG server
EXPOSE 8000 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "app.py"]
