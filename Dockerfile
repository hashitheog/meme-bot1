
# Use an official Python runtime with Playwright pre-installed (huge time saver)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set work directory
WORKDIR /app

# Install system dependencies if any extra are needed (Playwright image has most)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Firefox is critical for Nitter)
RUN playwright install firefox chromium

# Copy the rest of the app
COPY . .

# Create .env file from example if missing (User should provide real env in cloud)
# COPY .env.example .env 

# Command to run the bot
CMD ["python", "-m", "app.main"]
