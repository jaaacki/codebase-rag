FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    # for our little shell parser
    sed \
    awk \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Copy your .env into the image
COPY .env .

# Create the .streamlit folder and convert .env -> secrets.toml
RUN mkdir -p /app/.streamlit \
 && awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { \
      key=$1; val=$2; \
      # strip surrounding quotes/spaces
      gsub(/^["'\'']|["'\'']$/,"",val); \
      print key " = \"" val "\"" \
    }' .env > /app/.streamlit/secrets.toml

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chmod +x /app/start.sh \
 && sed -i 's/streamlit_app.py/app.py/g' /app/start.sh

EXPOSE 8501

CMD ["/app/start.sh"]
