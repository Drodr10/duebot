# A container = your code + its exact Python + its exact packages, frozen into
# one image that runs the same on your laptop, a friend's laptop, or a server.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer between code edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Secrets are NOT baked in. Pass them at run time:  docker run --env-file .env duebot
CMD ["python", "bot.py"]
