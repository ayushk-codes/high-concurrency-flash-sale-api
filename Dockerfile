# ARCHITECTURAL NOTE: Using the 'slim' variant. 
# This strips out unnecessary Debian compilation tools (like gcc), 
# which drastically reduces both the final image size and the security attack surface.
FROM python:3.11-slim

# Establish the working directory for all subsequent commands
WORKDIR /app

# NOTE: Dependency caching optimization.
# We copy ONLY the requirements file first. Docker caches layers, so if we don't change 
# our dependencies, Docker skips the expensive 'pip install' step on future builds.
COPY requirements.txt .

# PERFORMANCE: --no-cache-dir prevents pip from saving the downloaded .whl files, 
# keeping the container incredibly lightweight.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application logic
# CRITICAL: This command relies on a strict .dockerignore file to ensure 
# local .env files and __pycache__ are not baked into the image.
COPY . .

# Documentation for developers/orchestrators that this container listens on port 8000
EXPOSE 8000

# The strict execution command that starts the ASGI server bound to all network interfaces
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]