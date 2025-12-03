# ORCID Publication Counter

A Flask-based web application for extracting and analyzing publications from ORCID profiles with automatic join year detection from faculty Excel sheets.

## Features

✨ **Key Capabilities:**
- Upload Excel files with faculty information (name, ORCID, join date)
- Extract publication data from ORCID profiles
- Automatic join year detection to filter publications from join date onwards
- Support for journal articles, books, and book chapters
- Citation count retrieval from multiple sources
- Batch processing of multiple faculty members
- Export results to Excel files

## System Requirements

- **Python:** 3.8 or higher
- **OS:** Windows, macOS, or Linux
- **Memory:** 2GB minimum
- **Internet:** Required for ORCID and API access

## Installation

### Option 1: Using Python directly (Recommended)

1. **Download the application** from the repository
2. **Extract the folder** to your desired location
3. **Open terminal/command prompt** and navigate to the application folder:
   ```bash
   cd /path/to/orcid-publication-counter
   ```

4. **Install dependencies** (first time only):
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application:**
   ```bash
   python run.py
   ```

The application will automatically open in your default browser at `http://localhost:5000`

### Option 2: Using the executable (Windows only)

1. Download the `.exe` file
2. Double-click to run (no installation needed)
3. The application will start automatically

## Usage

### Step 1: Upload Faculty Data

1. Open the application (it will be running at `http://localhost:5000`)
2. Click **"Upload Excel File"**
3. Select your Excel file containing:
   - **Name** column: Faculty member name
   - **ORCID ID** column: ORCID identifier (format: 0000-0000-0000-0000)
   - **Join Date** or **Join Year** column: When they joined

4. The application will:
   - Extract join years automatically
   - Process all ORCIDs in the file
   - Fetch publications from each professor
   - Generate an Excel file with results

### Step 2: Single ORCID Search (Optional)

1. Enter a single ORCID ID in the search box
2. Click **Search**
3. View the publications for that person
4. The system will use the cached join year (if uploaded) or default to 2000

## Excel File Format

**Required Columns:**
| Column Name | Format | Example |
|---|---|---|
| Name | Text | John Smith |
| ORCID ID | XXXX-XXXX-XXXX-XXXX | 0000-0001-2345-6789 |
| Join Date | Date (DD/MM/YYYY) | 15/01/2018 |
| OR Join Year | Number | 2018 |

**Example File Structure:**
```
No | Name | ORCID ID | Join Date | Subject Area
1  | John Smith | 0000-0001-2345-6789 | 01/01/2018 | Computer Science
2  | Jane Doe | 0000-0002-3456-7890 | 15/06/2020 | Physics
```

## Output Format

The generated Excel file includes:

**For Journal Articles:**
- All Authors
- Authors in School
- Article Title
- DOI
- Year
- Journal Title
- Publication Date
- Citation Count

**For Books & Chapters:**
- Authors
- Title
- Year
- Publisher
- Citation Count
- Publication Date

## Troubleshooting

### Application won't start
```bash
# Make sure Python 3.8+ is installed
python --version

# Try running with explicit Python path
python3 run.py
```

### Dependencies not installed
```bash
# Reinstall all requirements
pip install --upgrade -r requirements.txt
```

### ORCID not found in cache
- Make sure you uploaded an Excel file first
- The ORCID must be in the uploaded file
- Restart the application if needed

### Port 5000 already in use
- Close other applications using port 5000
- Or edit `run.py` to use a different port (change PORT = 5000)

## Data Privacy

- All processing is done locally on your computer
- No data is stored on external servers
- Only ORCID API calls are made to fetch public profile information

## Support

For issues or questions, please check:
1. Ensure your Excel file has the required columns
2. Verify ORCIDs are in the correct format (XXXX-XXXX-XXXX-XXXX)
3. Check your internet connection for API access

## License

This project uses public APIs from ORCID, CrossRef, and OpenAlex for research purposes.

## Contact

For questions or feedback about this application, please contact your institution's research office.

---

**Version:** 1.0.0  
**Last Updated:** November 2025
