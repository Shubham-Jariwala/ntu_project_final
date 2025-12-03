# Distribution Guide for ORCID Publication Counter

## 📦 How to Package Your Application

### Method 1: Simple Distribution (Recommended for users with Python)

1. **Create a project folder** with all your files:
   ```
   orcid-publication-counter/
   ├── app.py
   ├── paper_count.py
   ├── paper.py
   ├── run.py
   ├── run.sh
   ├── run.bat
   ├── requirements.txt
   ├── setup.py
   ├── README.md
   ├── templates/
   │   └── index.html
   ├── static/
   └── .gitignore
   ```

2. **Create a ZIP file** with all the above files

3. **Create an installation guide** (INSTALL.md):
   ```markdown
   # Installation Instructions
   
   ## For Windows Users
   - Download and extract the ZIP file
   - Double-click `run.bat`
   - The application will start automatically
   
   ## For macOS Users
   - Download and extract the ZIP file
   - Open Terminal
   - Run: `bash run.sh`
   
   ## For Linux Users
   - Download and extract the ZIP file
   - Open Terminal
   - Run: `bash run.sh`
   
   **First run will install dependencies (requires internet)**
   ```

4. **Distribution:**
   - Upload ZIP to GitHub Releases
   - Share via Google Drive / OneDrive
   - Host on your institution's website

---

### Method 2: Create Windows Executable (.exe)

**Tools needed:** PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable (run from project folder)
pyinstaller --onefile \
    --windowed \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --icon="icon.ico" \
    run.py
```

**Output:** `dist/run.exe` (standalone executable)

---

### Method 3: Create macOS Executable (.app)

```bash
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Create macOS app bundle
pyinstaller --onefile \
    --windowed \
    --osx-bundle-identifier=com.ntu.orcid-counter \
    --add-data "templates:templates" \
    --add-data "static:static" \
    run.py

# Result: dist/run.app
```

---

### Method 4: Pip Package Distribution

1. **Create account on PyPI:**
   - Visit https://pypi.org/
   - Create account
   - Get API token

2. **Build distribution:**
   ```bash
   pip install build
   python -m build
   ```

3. **Upload to PyPI:**
   ```bash
   pip install twine
   twine upload dist/*
   ```

4. **Users install via:**
   ```bash
   pip install orcid-publication-counter
   orcid-counter
   ```

---

### Method 5: Docker Container (For servers)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
```

Build and run:
```bash
docker build -t orcid-counter .
docker run -p 5000:5000 orcid-counter
```

---

## 📋 Checklist Before Distribution

- [ ] Test on Windows
- [ ] Test on macOS  
- [ ] Test on Linux
- [ ] Update version number in `setup.py`
- [ ] Create comprehensive README.md
- [ ] Test with sample Excel file
- [ ] Document known issues
- [ ] Add CHANGELOG.md
- [ ] Add LICENSE.md
- [ ] Create installation video (optional)

---

## 🚀 Recommended Distribution Method for You

**For your use case, use Method 1 (Simple Distribution):**

### Step-by-step:

1. **Create release folder:**
   ```bash
   mkdir orcid-publication-counter-v1.0.0
   cp -r *.py *.txt *.md run.* templates/ static/ orcid-publication-counter-v1.0.0/
   ```

2. **Create ZIP:**
   ```bash
   zip -r orcid-publication-counter-v1.0.0.zip orcid-publication-counter-v1.0.0/
   ```

3. **Upload to GitHub:**
   - Create GitHub repository
   - Push code
   - Create Release with ZIP download

4. **Create quick start guide:**
   - Windows: `run.bat` (just double-click)
   - macOS/Linux: `bash run.sh`

---

## 📖 Create INSTALL.md File

```markdown
# Quick Start Guide

## Windows
1. Extract the ZIP file
2. Double-click `run.bat`
3. Wait for browser to open (first run installs packages)
4. Done! ✓

## macOS
1. Extract the ZIP file
2. Open Terminal
3. Navigate to folder: `cd /path/to/orcid-publication-counter`
4. Run: `bash run.sh`
5. Browser opens automatically

## Linux
Same as macOS - use `bash run.sh`

## Troubleshooting
- Make sure Python 3.8+ is installed
- Check internet connection (first run needs to download packages)
- Port 5000 must be available
```

---

## 💡 Pro Tips

1. **Add version info** to `app.py`:
   ```python
   APP_VERSION = "1.0.0"
   ```

2. **Add about page** to show version in web UI

3. **Create sample Excel file** to include with distribution

4. **Add auto-update checker** (optional)

5. **Create video tutorial** for distribution

---

## 📊 Popular Distribution Options

| Option | Ease | Users | Cost |
|--------|------|-------|------|
| ZIP + GitHub | ⭐⭐⭐ | Developers | Free |
| ZIP + Google Drive | ⭐⭐⭐ | Non-technical | Free |
| .exe Installer | ⭐ | Windows users | Free* |
| PyPI Package | ⭐⭐ | Developers | Free |
| Docker | ⭐⭐ | DevOps teams | Free |

*May need code signing for Windows

---

**For your project, I recommend: Simple ZIP distribution via GitHub Releases** ✓
