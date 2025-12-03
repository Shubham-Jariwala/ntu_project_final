# Vercel serverless function entry point
import sys
import os

# Add parent directory to path to import app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import the Flask app
from app import app

# Vercel expects the app to be exported
# The Flask app is now available as 'app'
