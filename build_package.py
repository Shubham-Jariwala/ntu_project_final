#!/usr/bin/env python3
"""
Build script for creating distribution packages
Run: python build_package.py
"""
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_distribution_package():
    """Create a distributable ZIP package"""
    
    # Define project structure
    project_dir = Path(__file__).parent
    package_name = "orcid-publication-counter"
    version = "1.0.0"
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_name = f"{package_name}-v{version}-{timestamp}.zip"
    
    # Files to include
    files_to_include = [
        'app.py',
        'paper_count.py',
        'paper.py',
        'run.py',
        'run.sh',
        'run.bat',
        'requirements.txt',
        'setup.py',
        'README.md',
        'DISTRIBUTION_GUIDE.md',
        '.gitignore',
    ]
    
    # Directories to include
    dirs_to_include = [
        'templates',
        'static',
    ]
    
    # Create distribution folder
    dist_folder = project_dir / "dist" / f"{package_name}-v{version}"
    dist_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Creating distribution package: {zip_name}")
    print(f"📁 Package location: {dist_folder}")
    
    # Copy files
    print("\n📋 Copying files...")
    for file in files_to_include:
        src = project_dir / file
        if src.exists():
            dst = dist_folder / file
            shutil.copy2(src, dst)
            print(f"  ✓ {file}")
        else:
            print(f"  ⚠️  Missing: {file}")
    
    # Copy directories
    print("\n📁 Copying directories...")
    for dir_name in dirs_to_include:
        src = project_dir / dir_name
        if src.exists():
            dst = dist_folder / dir_name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  ✓ {dir_name}/")
    
    # Create README for distribution
    print("\n📝 Creating installation guide...")
    install_guide = dist_folder / "INSTALL.md"
    install_guide.write_text("""# ORCID Publication Counter - Installation Guide

## Quick Start

### Windows Users
1. Extract this folder
2. Double-click `run.bat`
3. The application will open automatically in your browser

### macOS Users
1. Extract this folder
2. Open Terminal
3. Run: `bash run.sh`

### Linux Users
1. Extract this folder
2. Open Terminal  
3. Run: `bash run.sh`

## First Run

The first run may take a minute as it installs required packages.
This only happens once.

## System Requirements

- Python 3.8 or higher
- 2GB RAM minimum
- Internet connection

## Troubleshooting

**Python not found:**
- Install from https://www.python.org/downloads/
- Check "Add Python to PATH" during installation

**Port 5000 in use:**
- Close other applications using that port
- Or edit run.py to change PORT

**Need help?**
- Check README.md for detailed documentation
- See DISTRIBUTION_GUIDE.md for more info
""")
    print(f"  ✓ INSTALL.md")
    
    # Create ZIP file
    print(f"\n📦 Creating ZIP file...")
    zip_path = project_dir / "dist" / zip_name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_folder):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(dist_folder.parent)
                zipf.write(file_path, arcname)
    
    print(f"  ✓ {zip_name} created")
    print(f"  ✓ Size: {zip_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Create summary
    print("\n" + "="*65)
    print("✅ Distribution package created successfully!")
    print("="*65)
    print(f"\n📦 Package: {zip_name}")
    print(f"📍 Location: {zip_path}")
    print(f"\n📤 Ready to distribute!")
    print(f"   - Upload to GitHub Releases")
    print(f"   - Share via Google Drive")
    print(f"   - Post on your website")
    print("\n")

if __name__ == '__main__':
    try:
        create_distribution_package()
    except Exception as e:
        print(f"❌ Error creating package: {e}")
        exit(1)
