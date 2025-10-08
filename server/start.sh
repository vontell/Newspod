#!/bin/bash
# Newspod Server Startup Script

set -e

echo "🚀 Starting Newspod Server..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Add the parent directory to Python path so we can import newsletter_podcast
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

# Start the server
echo "🎯 Starting FastAPI server..."
python app.py