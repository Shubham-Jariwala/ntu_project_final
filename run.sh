#!/bin/bash
# ORCID Publication Counter - macOS/Linux Launcher

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the application directory
cd "$DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "✓ Python version: $PYTHON_VERSION"

# Check if requirements are installed
echo "Checking dependencies..."
python3 -c "import flask; import pandas; import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip3 install -r requirements.txt
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        ORCID Publication Counter - Starting Application        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Application running at: http://localhost:5000"
echo "🔗 Opening in your default browser..."
echo "⚠️  Press CTRL+C to stop the application"
echo ""

# Open browser (macOS and Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:5000" 2>/dev/null
else
    xdg-open "http://localhost:5000" 2>/dev/null || echo "Please open http://localhost:5000 in your browser"
fi

# Run the application
python3 run.py
