#!/usr/bin/env python3
"""
ORCID Publication Counter - Executable Launcher
This script starts the Flask web application.
"""
import os
import sys
import webbrowser
from pathlib import Path

def main():
    # Get the application directory
    app_dir = Path(__file__).parent
    os.chdir(app_dir)
    
    # Import Flask app
    from app import app
    
    # Configuration
    HOST = '127.0.0.1'
    PORT = 5000
    URL = f'http://{HOST}:{PORT}'
    
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║        ORCID Publication Counter - Starting Application        ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    print(f"📚 Opening application at: {URL}")
    print("🔗 The application window will open in your default browser")
    print("⚠️  Close the browser tab and return here to stop the application")
    print("-" * 65)
    
    # Open browser automatically
    webbrowser.open(URL)
    
    # Run the Flask app
    try:
        app.run(host=HOST, port=PORT, debug=False)
    except KeyboardInterrupt:
        print("\n\n✋ Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
