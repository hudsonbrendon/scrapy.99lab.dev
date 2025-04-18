FROM python:3.13-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock main.py ./
COPY README.md ./

# Install dependencies
RUN pip install --upgrade pip && \
    pip install .

# Expose the port for the FastAPI application
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]