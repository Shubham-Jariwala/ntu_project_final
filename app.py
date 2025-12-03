from flask import Flask, render_template, request, send_file, redirect, url_for, flash, session
import pandas as pd
import requests
import json
from paper_count import GetPublicationsByName, GetCitedByCountFromOpenAlex, GetPublicationsFromORCID, _get_publications_from_orcid
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB upload limit
app.secret_key = 'replace-this-with-a-secure-random-key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# In-memory cache for faculty data (survives across requests without session complexity)
# In-memory cache
# A simple module-level dict that stores ORCID -> {'join_year','join_month'}.
# Declared here so all request handlers can read/write it without NameError.
# Also keep a set of known faculty names (lowercase) populated by uploads
faculty_cache = {}
faculty_names = set()

def compute_stats(publications, start_year=2000, end_year=2050):
    """Compute basic stats for charts and display.

    publications: dict with keys like 'journal','book','chapter', each a list of dicts
    start_year: integer year to start yearly buckets
    Returns a dict serializable to JSON with total_citations, oa_counts, yearly_citations, top_works
    """
    stats = {
        "total_citations": 0,
        "source_counts": {"ORCID": 0, "CrossRef": 0, "OpenAlex": 0, "Google Scholar": 0, "Unknown": 0},
        "yearly_citations": {},
        "top_works": []
    }
    try:
        end_year = int(end_year)
        for y in range(int(start_year), end_year + 1):
            stats["yearly_citations"][str(y)] = 0

        works_for_ranking = []

        for cat, pubs in (publications or {}).items():
            for p in pubs:
                # citation count
                cit = None
                for k in ("Citation Count", "citation_count", "cited_by_count", "Cited By Count"):
                    if k in p and p.get(k) is not None:
                        try:
                            cit = int(p.get(k) or 0)
                        except Exception:
                            cit = None
                        break

                if cit:
                    stats["total_citations"] += cit

                # try to get year
                pub_year = None
                for key in ("Year", "year", "publication_date", "Publication Date"):
                    if key in p and p.get(key):
                        try:
                            pub_year = int(str(p.get(key))[:4])
                        except Exception:
                            pub_year = None
                        break

                if pub_year and start_year <= pub_year <= end_year:
                    stats["yearly_citations"][str(pub_year)] += int(cit or 0)

                # Track source distribution
                source = p.get("source") or "Unknown"
                if source in stats["source_counts"]:
                    stats["source_counts"][source] += 1
                else:
                    stats["source_counts"]["Unknown"] += 1

                # top works
                title = p.get("Article Title") or p.get("Title") or p.get("Book Title") or p.get("Chapter Title") or "Untitled"
                works_for_ranking.append((title, int(cit or 0)))

        works_for_ranking.sort(key=lambda x: x[1], reverse=True)
        stats["top_works"] = works_for_ranking[:10]
    except Exception:
        # on any failure return minimal stats
        pass
    return stats


@app.route('/', methods=['GET', 'POST'])
def index():
    publications = None
    prof_name = ''
    error = None
    stats = None

    if request.method == 'POST':
        prof_name = request.form.get('prof_name', '').strip()
        # Get year inputs and convert to full dates
        start_year = request.form.get('start_year', '2000')
        end_year = request.form.get('end_year', '2050')
        start_date_str = f"{start_year}-01-01"
        end_date_str = f"{end_year}-12-31"
        if prof_name:
            try:
                print(f"DEBUG index: About to call GetPublicationsByName with prof_name={prof_name}, start_year={start_year}, end_year={end_year}")
                pubs = GetPublicationsByName(prof_name, start_date_str, end_date_str)
                publications = pubs
                # compute stats using start year derived from start_date_str
                try:
                    parsed = pd.to_datetime(start_date_str, errors='coerce')
                    start_year_val = int(parsed.year) if not pd.isna(parsed) else 2000
                except Exception:
                    start_year_val = 2000
                # derive end year from end_date_str and pass both start & end to compute_stats
                try:
                    parsed_end = pd.to_datetime(end_date_str, errors='coerce')
                    end_year_val = int(parsed_end.year) if not pd.isna(parsed_end) else 2050
                except Exception:
                    end_year_val = 2050
                stats = compute_stats(publications, start_year=start_year_val, end_year=end_year_val)
            except Exception as e:
                error = f"Error extracting publications: {e}"
        else:
            error = "Please enter a professor name."

    cache_info = f"Faculty cache has {len(faculty_cache)} ORCIDs loaded" if faculty_cache else "No faculty data loaded yet. Upload an Excel file first."
    print(f"DEBUG: Rendering index page with cache_info: {cache_info}")
    print(f"   Current faculty_cache contents: {dict(list(faculty_cache.items())[:3])}")  # Show first 3
    return render_template('index.html', prof_name=prof_name, publications=publications, error=error, cache_info=cache_info, stats=stats)

def _find_column(df, keywords):
    """Find first column name in df that contains any of the keywords (case-insensitive)."""
    for col in df.columns:
        low = str(col).lower()
        for k in keywords:
            if k in low:
                return col
    return None


def _detect_orcid_column(df, sample_size=50, threshold=0.25):
    """Detect column that likely contains ORCID values.

    Strategy:
    - First try header names (handled by _find_column).
    - Then sample values from each column and check if a reasonable fraction
      match ORCID patterns (hyphenated 0000-0000-0000-0000 or orcid.org URLs).
    - Returns column name or None.
    """
    import re
    orcid_regex = re.compile(r"(\b\d{4}-\d{4}-\d{4}-\d{3,4}\b)")
    url_regex = re.compile(r"orcid\.org", re.IGNORECASE)

    for col in df.columns:
        vals = df[col].dropna().astype(str)
        if vals.empty:
            continue
        # sample up to sample_size values
        sample = vals.sample(n=min(len(vals), sample_size), random_state=1)
        matches = 0
        for v in sample:
            v = v.strip()
            if not v:
                continue
            if orcid_regex.search(v) or url_regex.search(v):
                matches += 1
        if len(sample) > 0 and (matches / len(sample)) >= threshold:
            return col
    return None


def _detect_scholar_column(df):
    """Try to detect a Google Scholar identifier or URL column by header or value patterns."""
    keywords = ['scholar', 'google scholar', 'gsid', 'scholar_id', 'scholar id', 'scholar url']
    col = _find_column(df, keywords)
    if col:
        return col
    # try value scan for typical scholar URL pattern
    import re
    url_re = re.compile(r"scholar\.google\.com/(citations|scholar)" , re.IGNORECASE)
    for c in df.columns:
        vals = df[c].dropna().astype(str)
        if vals.empty:
            continue
        sample = vals.sample(n=min(len(vals), 30), random_state=1)
        matches = 0
        for v in sample:
            if url_re.search(v):
                matches += 1
        if matches > 0:
            return c
    return None


def _get_scholar_citation_count(profile_url_or_id):
    """Best-effort scraping of Google Scholar profile to extract total citation count.

    Accepts either a full profile URL or a 'user' id. Returns int or None.
    This is best-effort and may fail due to blocking or layout changes.
    """
    try:
        val = str(profile_url_or_id).strip()
        if not val:
            return None
        # if just a user id (short string), build profile URL
        if 'scholar.google' not in val.lower():
            # assume it is a user id
            val = f"https://scholar.google.com/citations?user={urllib.parse.quote(val)}&hl=en"
        # fetch page
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36"}
        r = requests.get(val, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        # citations table has id 'gsc_rsb_st'
        table = soup.find('table', {'id': 'gsc_rsb_st'})
        if table:
            # first row is 'Citations' and first numeric cell contains total
            row = table.find('tr')
            if row:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    txt = cells[1].get_text(strip=True).replace(',', '')
                    try:
                        return int(txt)
                    except Exception:
                        return None
        # fallback: look for element with class 'gsc_rsb_std'
        stds = soup.find_all('td', {'class': 'gsc_rsb_std'})
        if stds:
            try:
                txt = stds[0].get_text(strip=True).replace(',', '')
                return int(txt)
            except Exception:
                return None
    except Exception:
        return None
    return None


def _search_openalex_author_by_name(name, max_retries=3):
    """Search OpenAlex authors by name and return the best match with citation metrics.

    Uses the 'search' parameter for fuzzy name matching. Returns dict with 'id', 'display_name',
    'cited_by_count', 'works_count', 'h_index', 'i10_index' on success, or None on failure.
    Includes retry logic for transient failures.
    """
    import time
    if not name or not str(name).strip():
        return None
    
    name_clean = str(name).strip()
    for attempt in range(max_retries):
        try:
            # Query OpenAlex authors API with search parameter (fuzzy match)
            url = 'https://api.openalex.org/authors'
            params = {
                'search': name_clean,
                'per-page': 10
            }
            q = requests.get(url, params=params, timeout=10)
            if q.status_code != 200:
                print(f"OpenAlex API returned {q.status_code} for name '{name_clean}'")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
                continue
            
            data = q.json()
            results = data.get('results', [])
            if not results:
                print(f"No OpenAlex results for name '{name_clean}'")
                return None
            
            # Choose best by exact display_name match (case-insensitive), else highest cited_by_count
            name_lower = name_clean.lower()
            best = None
            for a in results:
                display = a.get('display_name', '').strip().lower()
                if display == name_lower:
                    best = a
                    break
            
            if not best:
                # Pick highest cited_by_count
                results.sort(key=lambda x: x.get('cited_by_count', 0), reverse=True)
                best = results[0]
                print(f"Using fuzzy match for '{name_clean}': {best.get('display_name')} (citations: {best.get('cited_by_count')})")
            else:
                print(f"Exact match found for '{name_clean}': citations={best.get('cited_by_count')}")
            
            # Extract all relevant fields from author object
            summary_stats = best.get('summary_stats', {})
            return {
                'id': best.get('id'),
                'display_name': best.get('display_name'),
                'cited_by_count': best.get('cited_by_count', 0),
                'works_count': best.get('works_count', 0),
                'h_index': summary_stats.get('h_index'),
                'i10_index': summary_stats.get('i10_index'),
                'last_known_institutions': best.get('last_known_institutions', []),
                'orcid': best.get('orcid')  # In case OpenAlex found the ORCID
            }
        except Exception as e:
            print(f"OpenAlex search error for '{name_clean}' (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
            continue
    
    print(f"Failed to find author on OpenAlex after {max_retries} attempts: {name_clean}")
    return None


@app.route('/upload', methods=['POST'])
def upload():
    # Expect a file input named 'file' and optional sheet_name
    f = request.files.get('file')
    sheet_name = request.form.get('sheet_name') or 0
    # Optional user-specified start/end years for bulk processing (overrides join year)
    user_start_year_str = request.form.get('start_year', '').strip()
    user_end_year_str = request.form.get('end_year', '').strip()
    # We'll keep both full parsed datetimes (for exact range) and year fallbacks
    user_start_year = None
    user_end_year = None
    user_start_date_dt = None
    user_end_date_dt = None
    import datetime as _dt
    try:
        if user_start_year_str:
            user_start_year = int(user_start_year_str)
            user_start_date_dt = _dt.datetime(user_start_year, 1, 1)
    except Exception:
        user_start_year = None
        user_start_date_dt = None
    try:
        if user_end_year_str:
            user_end_year = int(user_end_year_str)
            user_end_date_dt = _dt.datetime(user_end_year, 12, 31)
    except Exception:
        user_end_year = None
        user_end_date_dt = None
    if not f:
        flash('No file uploaded', 'danger')
        return redirect(url_for('index'))

    try:
        # Read Excel into DataFrame
        import io
        import pandas as pd
        file_bytes = f.read()
        excel = pd.ExcelFile(io.BytesIO(file_bytes))
        # default to first sheet if provided sheet_name not in workbook
        try:
            if sheet_name and isinstance(sheet_name, str) and sheet_name.isdigit():
                sheet_name = int(sheet_name)
            if sheet_name not in excel.sheet_names and isinstance(sheet_name, str):
                sheet_name = excel.sheet_names[0]
        except Exception:
            sheet_name = excel.sheet_names[0]

        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)

        # If the sheet uses a non-zero header row (e.g., your sample uses header=2),
        # try to detect the correct header by scanning the first few rows for a 'Join' column.
        preferred_join_cols = ['Join Date', 'Join Year', 'Join', 'join date', 'join']
        found_join = False
        for header_row in range(0, 5):
            try:
                tmp = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=header_row)
            except Exception:
                continue
            for col in tmp.columns:
                low = str(col).strip().lower()
                for k in preferred_join_cols:
                    if k.lower() == low:
                        df = tmp
                        found_join = True
                        break
                if found_join:
                    break
            if found_join:
                print(f"DEBUG: Detected header row={header_row} based on join column")
                break

        # Locate likely columns
        orcid_col = _find_column(df, ['orcid'])
        name_col = _find_column(df, ['name', 'employee', 'full name'])
        # Prefer exact column names if present (user sample uses 'Join Date' / 'Join Year')
        # Use case-insensitive matching
        preferred_join_cols = ['join date', 'join year', 'join', 'start date']
        join_col = None
        for c in df.columns:
            if str(c).strip().lower() in preferred_join_cols:
                join_col = c
                break
        if join_col is None:
            join_col = _find_column(df, ['join', 'join date', 'start date', 'joined'])
        print(f"DEBUG: Available columns: {list(df.columns)}")
        print(f"DEBUG: Detected orcid_col={orcid_col!r}, name_col={name_col!r}, join_col={join_col!r}")

        # Try to detect a Google Scholar column (optional)
        scholar_col = _detect_scholar_column(df)

        # Pre-parse join date column (vectorized) so year/month are reliable
        if join_col and join_col in df.columns:
            print(f"DEBUG: Attempting vectorized parse of join_col={join_col!r}")
            try:
                # If the column already contains year values (e.g., 'Join Year'), coerce appropriately
                if 'year' in str(join_col).lower() and pd.api.types.is_numeric_dtype(df[join_col]):
                    df['_parsed_join_year'] = df[join_col].astype('Int64')
                    df['_parsed_join_month'] = None
                    print(f"DEBUG: Parsed numeric Join Year column")
                else:
                    df[join_col] = pd.to_datetime(df[join_col], errors='coerce')
                    df['_parsed_join_year'] = df[join_col].dt.year
                    df['_parsed_join_month'] = df[join_col].dt.month
                    print(f"DEBUG: Parsed datetime join column to year/month")
            except Exception as e:
                print(f"DEBUG: Vectorized join parse failed: {e}")
                df['_parsed_join_year'] = None
                df['_parsed_join_month'] = None
        else:
            print(f"DEBUG: No join_col found or not in df.columns")

        # If header-based detection failed, scan values for ORCID-like patterns
        if orcid_col is None:
            orcid_col = _detect_orcid_column(df)
            if orcid_col:
                pass
            else:
                flash('Could not find ORCID column in uploaded file', 'danger')
                return redirect(url_for('index'))

        # Load faculty join years directly from the main uploaded file using LoadFacultyJoinYears
        faculty_map_by_orcid = {}
        faculty_map_by_name = {}
        faculty_df_info = None
        try:
            from paper_count import LoadFacultyJoinYears
            # Use the main uploaded file to extract join years
            # Try to detect the correct sheet and header
            main_sheet = sheet_name if sheet_name else excel.sheet_names[0]
            faculty_map_by_orcid, faculty_map_by_name, faculty_df_info = LoadFacultyJoinYears(
                file_bytes,
                sheet_name=main_sheet,
                header=0 if not found_join else df.columns.tolist().index(join_col) if join_col in df.columns else 0
            )
            print(f"DEBUG: Loaded faculty join years from main file: orcid={len(faculty_map_by_orcid)} names={len(faculty_map_by_name)}")
            
            # ✅ POPULATE CACHE EARLY - right after loading faculty years
            global faculty_cache
            faculty_cache.clear()
            for orcid, data in faculty_map_by_orcid.items():
                faculty_cache[str(orcid)] = {
                    'join_year': int(data.get('join_year')) if data.get('join_year') is not None else None,
                    'join_month': int(data.get('join_month')) if data.get('join_month') is not None else None
                }
            # Populate faculty_names from mapping by name (lowercased)
            try:
                global faculty_names
                faculty_names.clear()
                for name in faculty_map_by_name.keys():
                    if name and isinstance(name, str):
                        faculty_names.add(name.strip().lower())
            except Exception:
                pass
            print(f"✅ DEBUG: Populated faculty cache EARLY with {len(faculty_cache)} ORCIDs")
            print(f"   Cache keys: {list(faculty_cache.keys())[:5]}")  # Show first 5
            
        except Exception as e:
            print(f"DEBUG: Failed to load faculty join years from main file: {e}")

        # Optionally load a separate faculty file mapping (form field 'faculty_file') to override
        faculty_file = request.files.get('faculty_file')
        if faculty_file:
            try:
                from paper_count import LoadFacultyJoinYears
                faculty_bytes = faculty_file.read()
                faculty_map_by_orcid, faculty_map_by_name, faculty_df_info = LoadFacultyJoinYears(faculty_bytes)
                print(f"DEBUG: Loaded faculty mapping from separate file: orcid={len(faculty_map_by_orcid)} names={len(faculty_map_by_name)}")
                try:
                    # also merge into faculty_names
                    for name in faculty_map_by_name.keys():
                        if name and isinstance(name, str):
                            faculty_names.add(name.strip().lower())
                except Exception:
                    pass
            except Exception as e:
                print(f"DEBUG: Failed to load separate faculty mapping file: {e}")

        # Prepare aggregated lists
        journal_rows = []
        book_rows = []
        chapter_rows = []
        profiles_rows = []  # for fallbacks: name/scholar -> citation counts
        failed_orcids = []

        # throttling / retry config for per-ORCID calls
        per_orcid_max_retries = 4
        per_orcid_retry_delay = 6  # seconds base for exponential backoff
        per_orcid_min_sleep = 0.2  # small sleep inside worker to avoid tight loops

        total_orcids = 0
        succeeded_orcids = 0

        # Build list of rows to process: include rows that have ORCID, or scholar id/url, or a name (for fallback)
        rows_to_process = []
        for idx, row in df.iterrows():
            orcid = row.get(orcid_col) if orcid_col in df.columns else None
            scholar_val = row.get(scholar_col) if (scholar_col and scholar_col in df.columns) else None
            prof_name = row.get(name_col) if name_col else None
            # Skip rows with no identifiers and no name
            if (not orcid or (isinstance(orcid, float) and pd.isna(orcid))) and (not scholar_val or (isinstance(scholar_val, float) and pd.isna(scholar_val))) and (not prof_name or (isinstance(prof_name, float) and pd.isna(prof_name))):
                continue

            # Use pre-parsed join year/month if available (faster and more robust)
            join_val = row.get(join_col) if join_col else None
            join_year = None
            join_month = None
            if '_parsed_join_year' in df.columns:
                try:
                    parsed_year = df.at[idx, '_parsed_join_year']
                    parsed_month = df.at[idx, '_parsed_join_month']
                    if not pd.isna(parsed_year):
                        join_year = int(parsed_year)
                    if not pd.isna(parsed_month):
                        join_month = int(parsed_month)
                    if join_year is not None:
                        print(f"DEBUG: Using parsed join year for prof={prof_name!r}: join_val={join_val!r} -> join_year={join_year} join_month={join_month}")
                except Exception:
                    # fall back to per-row parsing
                    try:
                        if join_val is not None and not pd.isna(join_val):
                            ts = pd.to_datetime(join_val, errors='coerce')
                            if not pd.isna(ts):
                                join_year = int(ts.year)
                                join_month = int(ts.month)
                                print(f"DEBUG: Fallback parsed join_val={join_val!r} -> join_year={join_year} join_month={join_month} for prof {prof_name!r}")
                    except Exception:
                        pass
            else:
                # No pre-parsed column present; parse per-row
                try:
                    if join_val is not None and not pd.isna(join_val):
                        ts = pd.to_datetime(join_val, errors='coerce')
                        if not pd.isna(ts):
                            join_year = int(ts.year)
                            join_month = int(ts.month)
                            print(f"DEBUG: Parsed join_val={join_val!r} -> join_year={join_year} join_month={join_month} for prof {prof_name!r}")
                except Exception:
                    pass
            # If join date wasn't provided or parsing failed, log that explicitly
            if join_year is None:
                print(f"DEBUG: No valid join_year extracted for prof={prof_name!r}; join_val={join_val!r}")
                # Try faculty mapping (by ORCID or by name)
                try:
                    # Try ORCID lookup first
                    orcid_lookup = None
                    if orcid_col in df.columns:
                        raw_orcid = row.get(orcid_col)
                        if raw_orcid is not None and not (isinstance(raw_orcid, float) and pd.isna(raw_orcid)):
                            orcid_lookup = str(raw_orcid).strip()
                    if orcid_lookup and orcid_lookup in faculty_map_by_orcid:
                        entry = faculty_map_by_orcid[orcid_lookup]
                        join_year = entry.get('join_year')
                        join_month = entry.get('join_month')
                        print(f"DEBUG: Filled join_year from faculty_map_by_orcid for prof={prof_name!r}: {join_year}")
                    elif prof_name and prof_name.strip().lower() in faculty_map_by_name:
                        entry = faculty_map_by_name[prof_name.strip().lower()]
                        join_year = entry.get('join_year')
                        join_month = entry.get('join_month')
                        print(f"DEBUG: Filled join_year from faculty_map_by_name for prof={prof_name!r}: {join_year}")
                except Exception as e:
                    print(f"DEBUG: faculty map lookup failed: {e}")
            rows_to_process.append({
                'row': row,
                'prof_name': prof_name,
                'join_year': join_year,
                'join_month': join_month,
                'scholar_val': scholar_val
            })

        total_orcids = len(rows_to_process)

        # Worker function to process a single row (suitable for threading)
        def _process_single(entry):
            import time, random
            row = entry['row']
            prof_name = entry['prof_name']
            join_year = entry['join_year']
            join_month = entry['join_month']
            scholar_val = entry.get('scholar_val')

            orcid = row.get(orcid_col) if orcid_col in df.columns else None
            orcid_str = ''
            if orcid is not None and not (isinstance(orcid, float) and pd.isna(orcid)):
                orcid_str = str(orcid).strip()
                try:
                    if 'orcid.org' in orcid_str.lower():
                        parts = orcid_str.replace('http://', '').replace('https://', '').split('/')
                        orcid_str = parts[-1] if parts[-1] else parts[-2]
                    orcid_str = orcid_str.strip().strip('<>').strip('"').strip("'")
                except Exception:
                    pass

            # Determine effective start/end datetimes for this entry
            # Priority: user-provided dates > defaults (ignore join_year for date range)
            import datetime as _dt
            try:
                if user_start_date_dt is not None:
                    start_dt = user_start_date_dt
                else:
                    start_dt = _dt.datetime(2000, 1, 1)

                if user_end_date_dt is not None:
                    end_dt = user_end_date_dt
                else:
                    end_dt = _dt.datetime(2050, 12, 31)
            except Exception:
                start_dt = _dt.datetime(2000, 1, 1)
                end_dt = _dt.datetime(2050, 12, 31)

            # If ORCID is present, fetch publications as before. Otherwise attempt fallbacks.
            if orcid_str:
                print(f"Processing ORCID: {orcid_str}")
                pubs = None
                last_error = None
                orcid_has_data = False
                from datetime import datetime, timezone
                for attempt in range(per_orcid_max_retries):
                    try:
                        # Use the already computed start_dt and end_dt from outside the retry loop
                        print(f"DEBUG: Calling ORCID fetch for orcid={orcid_str!r} prof={prof_name!r} start_dt={start_dt} end_dt={end_dt}")
                        # Use lower-level function that accepts full datetimes so we preserve month/day if user provided them
                        pubs = _get_publications_from_orcid(orcid_str, start_dt, end_dt)
                        if pubs is None:
                            raise ValueError('ORCID call returned None')
                        
                        # Check if publications dict has any actual data (not empty across all categories)
                        has_journal = bool(pubs.get('journal'))
                        has_book = bool(pubs.get('book'))
                        has_chapter = bool(pubs.get('chapter'))
                        orcid_has_data = has_journal or has_book or has_chapter
                        
                        if not orcid_has_data:
                            raise ValueError('ORCID record has no displayable data')
                        
                        time.sleep(per_orcid_min_sleep + random.uniform(0, 0.05))
                        print(f"Success fetching ORCID {orcid_str} on attempt {attempt+1}")
                        return {
                            'orcid': orcid_str,
                            'prof_name': prof_name,
                            'join_year': join_year,
                            'join_month': join_month,
                            'pubs': pubs,
                            'error': None,
                            'effective_start_year': int(start_dt.year) if start_dt is not None else None,
                            'effective_end_year': int(end_dt.year) if end_dt is not None else None
                        }
                    except Exception as e:
                        last_error = str(e)
                        sleep_time = per_orcid_retry_delay * (attempt + 1) + random.uniform(0, 0.5)
                        print(f"Attempt {attempt+1} failed for {orcid_str}: {last_error}. Retrying in {sleep_time:.1f}s...")
                        if attempt < per_orcid_max_retries - 1:
                            time.sleep(sleep_time)
                        else:
                            # ORCID failed or has no data: try fallback search
                            print(f"ORCID {orcid_str} failed or has no displayable data. Attempting fallback (scholar/name)...")
                            if scholar_val and not (isinstance(scholar_val, float) and pd.isna(scholar_val)):
                                sc_val = str(scholar_val).strip()
                                print(f"Attempting Google Scholar scrape for {prof_name}: {sc_val}")
                                cit = _get_scholar_citation_count(sc_val)
                                if cit is not None:
                                    print(f"Success: Found {cit} citations via Google Scholar for {prof_name}")
                                    return {
                                        'orcid': orcid_str,
                                        'prof_name': prof_name,
                                        'join_year': join_year,
                                        'join_month': join_month,
                                        'pubs': None,
                                        'profile_citations': cit,
                                        'profile_source': 'google_scholar',
                                        'profile_works_count': None,
                                        'profile_h_index': None,
                                        'profile_i10_index': None,
                                        'error': None,
                                        'used_fallback': True,
                                        'effective_start_year': int(start_dt.year) if start_dt is not None else None,
                                        'effective_end_year': int(end_dt.year) if end_dt is not None else None
                                    }
                                print(f"Google Scholar scrape failed for {prof_name}")
                            
                            # Try OpenAlex author search by name
                            if prof_name and str(prof_name).strip():
                                print(f"Attempting OpenAlex search for {prof_name}")
                                oa = _search_openalex_author_by_name(prof_name)
                                if oa:
                                    print(f"Success: Found OpenAlex author for {prof_name}")
                                    return {
                                            'orcid': orcid_str,
                                            'prof_name': prof_name,
                                            'join_year': join_year,
                                            'join_month': join_month,
                                            'pubs': None,
                                            'profile_citations': oa.get('cited_by_count'),
                                            'profile_source': 'openalex',
                                            'profile_openalex_id': oa.get('id'),
                                            'profile_works_count': oa.get('works_count'),
                                            'profile_h_index': oa.get('h_index'),
                                            'profile_i10_index': oa.get('i10_index'),
                                            'error': None,
                                            'used_fallback': True,
                                            'effective_start_year': int(start_dt.year) if start_dt is not None else None,
                                            'effective_end_year': int(end_dt.year) if end_dt is not None else None
                                        }
                                print(f"OpenAlex search failed for {prof_name}")
                            
                            # Fallback also failed - record error
                                return {
                                    'orcid': orcid_str,
                                    'prof_name': prof_name,
                                    'join_year': join_year,
                                    'join_month': join_month,
                                    'pubs': None,
                                    'error': last_error or 'Unknown error',
                                    'effective_start_year': int(start_dt.year) if start_dt is not None else None,
                                    'effective_end_year': int(end_dt.year) if end_dt is not None else None
                                }
            else:
                # No ORCID: try Google Scholar ID (if provided), then OpenAlex name search
                print(f"No ORCID for '{prof_name}'; attempting fallback (scholar/name)")
                # Try scholar profile first
                if scholar_val and not (isinstance(scholar_val, float) and pd.isna(scholar_val)):
                    sc_val = str(scholar_val).strip()
                    print(f"Attempting Google Scholar scrape for {prof_name}: {sc_val}")
                    cit = _get_scholar_citation_count(sc_val)
                    if cit is not None:
                        print(f"Success: Found {cit} citations via Google Scholar for {prof_name}")
                        return {
                            'orcid': None,
                            'prof_name': prof_name,
                            'join_year': join_year,
                            'join_month': join_month,
                            'pubs': None,
                            'profile_citations': cit,
                            'profile_source': 'google_scholar',
                            'profile_works_count': None,
                            'profile_h_index': None,
                            'profile_i10_index': None,
                            'error': None
                        }
                    print(f"Google Scholar scrape failed for {prof_name}")
                # Try OpenAlex author search by name
                if prof_name and str(prof_name).strip():
                    print(f"Attempting OpenAlex search for {prof_name}")
                    oa = _search_openalex_author_by_name(prof_name)
                    if oa:
                        print(f"Success: Found OpenAlex author for {prof_name}")
                        return {
                                            'orcid': None,
                                            'prof_name': prof_name,
                                            'join_year': join_year,
                                            'join_month': join_month,
                                            'pubs': None,
                                            'profile_citations': oa.get('cited_by_count'),
                                            'profile_source': 'openalex',
                                            'profile_openalex_id': oa.get('id'),
                                            'profile_works_count': oa.get('works_count'),
                                            'profile_h_index': oa.get('h_index'),
                                            'profile_i10_index': oa.get('i10_index'),
                                            'error': None,
                                            'effective_start_year': int(start_dt.year) if start_dt is not None else None,
                                            'effective_end_year': int(end_dt.year) if end_dt is not None else None
                                        }
                    print(f"OpenAlex search failed for {prof_name}")
                # nothing found
                print(f"No fallback source found for {prof_name}")
                return {
                    'orcid': None,
                    'prof_name': prof_name,
                    'join_year': join_year,
                    'join_month': join_month,
                    'pubs': None,
                    'profile_citations': None,
                    'profile_source': None,
                    'error': 'No ORCID and fallback search returned no results'
                }

        # Process up to 5 ORCIDs concurrently
        import concurrent.futures
        max_workers = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_entry = {executor.submit(_process_single, entry): entry for entry in rows_to_process}
            for fut in concurrent.futures.as_completed(future_to_entry):
                res = None
                entry = future_to_entry.get(fut)
                try:
                    res = fut.result()
                except Exception as e:
                    # Shouldn't usually happen because worker handles errors, but record if it does
                    orig_orcid = entry['row'].get(orcid_col) if entry else 'unknown'
                    failed_orcids.append({'ORCID': str(orig_orcid), 'Error': f'Worker crash: {e}'})
                    print(f"Worker crash for {orig_orcid}: {e}")
                    continue

                if res is None:
                    continue

                # If worker reported an error
                if res.get('error'):
                    # If ORCID was part of this row, record as failed ORCID; else record as failed profile lookup
                    if res.get('orcid'):
                        failed_orcids.append({'ORCID': res.get('orcid'), 'Error': res.get('error')})
                    else:
                        profiles_rows.append({
                            'Professor Name': res.get('prof_name'),
                            'Professor ORCID': None,
                            'Scholar Value': entry.get('scholar_val') if entry else None,
                            'Profile Source': res.get('profile_source'),
                            'Citations': res.get('profile_citations'),
                            'Works Count': res.get('profile_works_count'),
                            'H-Index': res.get('profile_h_index'),
                            'i10-Index': res.get('profile_i10_index'),
                            'Error': res.get('error')
                        })
                    continue

                # If publications returned, normalize and append as before
                pubs = res.get('pubs')
                if pubs:
                    orcid_str = res.get('orcid')
                    # Normalize returned shape
                    if pubs is not None and not isinstance(pubs, dict):
                        try:
                            if isinstance(pubs, list):
                                pubs = {"journal": pubs, "book": [], "chapter": []}
                            elif isinstance(pubs, tuple) and len(pubs) == 2 and isinstance(pubs[1], list):
                                pubs = {"journal": pubs[1], "book": [], "chapter": []}
                            else:
                                failed_orcids.append({'ORCID': orcid_str, 'Error': f'Unexpected ORCID response type: {type(pubs)}'})
                                pubs = None
                        except Exception as e:
                            failed_orcids.append({'ORCID': orcid_str, 'Error': f'Normalization error: {e}'})
                            pubs = None

                    if pubs is None:
                        continue

                    succeeded_orcids += 1
                    prof_name = res.get('prof_name')
                    join_year = res.get('join_year')
                    join_month = res.get('join_month')
                    # Determine start_year: prefer effective_start_year used for fetch (user override), else join_year, else default
                    eff_start = res.get('effective_start_year') if isinstance(res, dict) else None
                    if eff_start:
                        try:
                            start_year = int(eff_start)
                        except Exception:
                            start_year = None
                    else:
                        if join_year is not None and not (isinstance(join_year, float) and pd.isna(join_year)):
                            try:
                                start_year = int(join_year)
                            except Exception:
                                try:
                                    start_year = int(float(join_year))
                                except Exception:
                                    start_year = None
                        else:
                            start_year = None
                    if start_year is None:
                        start_year = 2000

                    for p in (pubs.get('journal') or []):
                        p_copy = dict(p)
                        p_copy['Professor Name'] = prof_name
                        p_copy['Professor ORCID'] = orcid_str
                        p_copy['Join Year'] = join_year
                        p_copy['Join Month'] = join_month
                        p_copy['Start Year'] = start_year
                        journal_rows.append(p_copy)

                    for p in (pubs.get('book') or []):
                        p_copy = dict(p)
                        p_copy['Professor Name'] = prof_name
                        p_copy['Professor ORCID'] = orcid_str
                        p_copy['Join Year'] = join_year
                        p_copy['Join Month'] = join_month
                        p_copy['Start Year'] = start_year
                        book_rows.append(p_copy)

                    for p in (pubs.get('chapter') or []):
                        p_copy = dict(p)
                        p_copy['Professor Name'] = prof_name
                        p_copy['Professor ORCID'] = orcid_str
                        p_copy['Join Year'] = join_year
                        p_copy['Join Month'] = join_month
                        p_copy['Start Year'] = start_year
                        chapter_rows.append(p_copy)
                else:
                    # No publications but worker returned profile citation info (fallback)
                    profiles_rows.append({
                        'Professor Name': res.get('prof_name'),
                        'Professor ORCID': res.get('orcid'),  # May have original ORCID even if used fallback
                        'Scholar Value': entry.get('scholar_val') if entry else None,
                        'Profile Source': res.get('profile_source'),
                        'Profile OpenAlex ID': res.get('profile_openalex_id'),
                        'Citations': res.get('profile_citations'),
                        'Works Count': res.get('profile_works_count'),
                        'H-Index': res.get('profile_h_index'),
                        'i10-Index': res.get('profile_i10_index'),
                        'Used Fallback': 'Yes' if res.get('used_fallback') else 'No',
                        'Error': None
                    })

        # Normalize, deduplicate and sort publication rows before writing output
        from statistics import mean
        from datetime import datetime

        def _normalize_row(p):
            # produce a normalized copy with canonical keys: 'All Authors', 'Citation Count', 'Publication Date', 'Article DOI', 'Article Title'
            r = dict(p)
            # Normalize DOI
            doi = r.get('Article DOI') or r.get('DOI') or r.get('doi') or r.get('ArticleDOI')
            if doi:
                doi = str(doi).strip()
                doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
                r['Article DOI'] = doi
            else:
                r['Article DOI'] = None

            # Normalize title
            title = r.get('Article Title') or r.get('Title') or r.get('Chapter Title') or r.get('Book Title')
            r['Article Title'] = title

            # Normalize authors
            authors = r.get('All Authors') or r.get('authors') or r.get('Authors') or r.get('authors_str')
            if not authors:
                # try authors_list
                a_list = r.get('authors_list') or r.get('Authors List') or []
                try:
                    names = []
                    for a in a_list:
                        if isinstance(a, dict):
                            n = a.get('name') or a.get('full_name')
                            if n:
                                names.append(str(n).strip())
                        elif isinstance(a, str):
                            names.append(a.strip())
                    if names:
                        authors = '; '.join(dict.fromkeys(names))
                except Exception:
                    authors = None
            if authors:
                # if comma-separated, convert to semicolon to be consistent
                if isinstance(authors, str):
                    authors = authors.replace(', ', '; ')
                r['All Authors'] = authors
            else:
                r['All Authors'] = None

            # Normalize citation count (collect many possible keys)
            counts = []
            for k in ('Citation Count', 'citation_count', 'cited_by_count', 'Cited By Count'):
                if k in r and r.get(k) is not None:
                    try:
                        counts.append(int(r.get(k)))
                    except Exception:
                        try:
                            counts.append(int(float(r.get(k))))
                        except Exception:
                            pass
            if counts:
                # use mean as requested
                try:
                    r['Citation Count'] = int(round(mean(counts)))
                except Exception:
                    r['Citation Count'] = counts[0]
            else:
                r['Citation Count'] = 0

            # Normalize publication date to ISO date string where possible
            pub_date_raw = r.get('Publication Date') or r.get('publication_date') or r.get('Year') or r.get('year')
            pub_dt = None
            if pub_date_raw:
                try:
                    # If it's already a datetime-like or timestamp, pandas will parse; try pd.to_datetime
                    pub_dt = pd.to_datetime(pub_date_raw, errors='coerce')
                except Exception:
                    pub_dt = None
            if pub_dt is not None and not pd.isna(pub_dt):
                # store ISO date string
                try:
                    r['Publication Date'] = pub_dt.strftime('%Y-%m-%d')
                except Exception:
                    r['Publication Date'] = str(pub_dt)
            else:
                # Try to coerce year-only values
                try:
                    y = int(str(pub_date_raw)[:4])
                    r['Publication Date'] = f"{y}-01-01"
                except Exception:
                    r['Publication Date'] = None

            return r

        def _dedupe_rows(rows):
            # dedupe using DOI if present, otherwise use normalized title
            keyed = {}
            for p in rows:
                r = _normalize_row(p)
                key = None
                if r.get('Article DOI'):
                    key = ('doi', r.get('Article DOI').lower())
                else:
                    t = r.get('Article Title') or ''
                    key = ('title', (str(t).strip().lower()))

                if key in keyed:
                    existing = keyed[key]
                    # merge citation counts
                    try:
                        existing_counts = existing.get('_merged_counts', [])
                        existing_counts.append(r.get('Citation Count') or 0)
                        existing['_merged_counts'] = existing_counts
                    except Exception:
                        pass
                    # merge authors
                    a1 = existing.get('All Authors') or ''
                    a2 = r.get('All Authors') or ''
                    merged_authors = []
                    for s in (a1, a2):
                        if s:
                            for name in [n.strip() for n in s.split(';') if n.strip()]:
                                if name not in merged_authors:
                                    merged_authors.append(name)
                    if merged_authors:
                        existing['All Authors'] = '; '.join(merged_authors)
                    # choose latest publication date
                    try:
                        d1 = pd.to_datetime(existing.get('Publication Date'), errors='coerce')
                        d2 = pd.to_datetime(r.get('Publication Date'), errors='coerce')
                        if d2 is not None and not pd.isna(d2) and (d1 is None or pd.isna(d1) or d2 > d1):
                            existing['Publication Date'] = r.get('Publication Date')
                    except Exception:
                        pass
                    # keep other non-null fields from existing
                    keyed[key] = existing
                else:
                    # initialize merged counts field
                    new = dict(r)
                    new['_merged_counts'] = [new.get('Citation Count') or 0]
                    keyed[key] = new

            # finalize merged results
            out = []
            for k, v in keyed.items():
                counts = v.pop('_merged_counts', [])
                if counts:
                    try:
                        v['Citation Count'] = int(round(mean([c for c in counts if isinstance(c, (int, float))])))
                    except Exception:
                        v['Citation Count'] = counts[0] if counts else 0
                else:
                    v['Citation Count'] = 0
                out.append(v)
            return out

        # Build output Excel in a temporary file
        import tempfile
        out_fd, out_path = tempfile.mkstemp(suffix='.xlsx')
        try:
            import os
            os.close(out_fd)
            with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
                # Desired display order for publication sheets. Keep any other columns after these.
                desired_cols = [
                    'All Authors',
                    'Authors in School',
                    'Professor ORCID',
                    'Article Title',
                    'Article DOI',
                    'Journal Title',
                    'Publication Date',
                    'Citation Count'
                ]

                def _reorder_df_preserve(df):
                    # Put desired columns first (if present), then any remaining columns
                    cols = [c for c in desired_cols if c in df.columns]
                    cols += [c for c in df.columns if c not in cols]
                    return df[cols]

                # Journal sheet - normalize, dedupe and sort newest-first
                journal_clean = _dedupe_rows(journal_rows)
                df_j = pd.DataFrame(journal_clean)
                if not df_j.empty:
                    # Remove internal columns not desired in output
                    df_j = df_j.drop(columns=['Professor Name', 'Join Year', 'Join Month', '_merged_counts'], errors='ignore')
                    # ensure Publication Date is datetime for sorting
                    if 'Publication Date' in df_j.columns:
                        df_j['__pub_dt'] = pd.to_datetime(df_j['Publication Date'], errors='coerce')
                        df_j = df_j.sort_values(by='__pub_dt', ascending=False).drop(columns=['__pub_dt'])
                    df_j = _reorder_df_preserve(df_j)
                df_j.to_excel(writer, sheet_name='Journal', index=False)

                # Book sheet - normalize, dedupe and sort newest-first
                book_clean = _dedupe_rows(book_rows)
                df_b = pd.DataFrame(book_clean)
                if not df_b.empty:
                    df_b = df_b.drop(columns=['Professor Name', 'Join Year', 'Join Month', '_merged_counts'], errors='ignore')
                    if 'Publication Date' in df_b.columns:
                        df_b['__pub_dt'] = pd.to_datetime(df_b['Publication Date'], errors='coerce')
                        df_b = df_b.sort_values(by='__pub_dt', ascending=False).drop(columns=['__pub_dt'])
                    df_b = _reorder_df_preserve(df_b)
                df_b.to_excel(writer, sheet_name='Book', index=False)

                # Chapter sheet - normalize, dedupe and sort newest-first
                chapter_clean = _dedupe_rows(chapter_rows)
                df_c = pd.DataFrame(chapter_clean)
                if not df_c.empty:
                    df_c = df_c.drop(columns=['Professor Name', 'Join Year', 'Join Month', '_merged_counts'], errors='ignore')
                    if 'Publication Date' in df_c.columns:
                        df_c['__pub_dt'] = pd.to_datetime(df_c['Publication Date'], errors='coerce')
                        df_c = df_c.sort_values(by='__pub_dt', ascending=False).drop(columns=['__pub_dt'])
                    df_c = _reorder_df_preserve(df_c)
                df_c.to_excel(writer, sheet_name='Chapter', index=False)

                # Profiles sheet removed as per user request (no longer writing profiles_rows)
                # write errors sheet so user can re-run or inspect failures
                if failed_orcids:
                    pd.DataFrame(failed_orcids).to_excel(writer, sheet_name='Errors', index=False)

            # Faculty cache was already populated early above when we loaded faculty join years
            print(f"✅ Faculty cache ready with {len(faculty_cache)} ORCIDs for single ORCID search")
            print(f"✅ Done! Successfully processed {succeeded_orcids} out of {total_orcids} entries.")
            
            # send file for download
            return send_file(out_path, as_attachment=True, download_name='publications_output.xlsx')
        finally:
            try:
                # remove file after sending is handled by Flask/wsgi; if not, ensure cleanup (best-effort)
                pass
            except Exception:
                pass

    except Exception as e:
        flash(f'Failed to process uploaded file: {e}', 'danger')
        return redirect(url_for('index'))


# Optimized the single search logic to aggregate data from multiple sources (ORCID, Google Scholar, CrossRef, OpenAlex).
# Added deduplication logic to ensure no duplicate entries are returned.

def search_publications(prof_name, start_date, end_date):
    """
    Search for publications by professor name across multiple sources:
    - ORCID
    - Google Scholar
    - CrossRef
    - OpenAlex

    Deduplicate results based on DOI or title.
    """
    from paper_count import _search_google_scholar, _search_crossref, _search_orcid_by_name, _search_openalex, _deduplicate_publications

    all_publications = []

    # Search ORCID
    orcid_pubs = _search_orcid_by_name(prof_name, start_date, end_date)
    all_publications.extend(orcid_pubs)

    # Search Google Scholar
    gs_pubs = _search_google_scholar(prof_name, start_date, end_date)
    all_publications.extend(gs_pubs)

    # Search CrossRef
    cr_pubs = _search_crossref(prof_name, start_date, end_date)
    all_publications.extend(cr_pubs)

    # Search OpenAlex
    oa_pubs = _search_openalex(prof_name, start_date, end_date)
    all_publications.extend(oa_pubs)

    # Deduplicate publications
    deduplicated_publications = _deduplicate_publications(all_publications)

    return deduplicated_publications

@app.route('/search', methods=['POST'])
def search():
    import re
    prof_name = request.form.get('prof_name', '').strip()
    # Get year inputs and convert to full dates
    start_year = request.form.get('start_year', '2000')
    end_year = request.form.get('end_year', '2050')
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    if not prof_name:
        return {'error': 'Please enter a professor name.'}, 400
    results = search_publications(prof_name, start_date, end_date)
    global faculty_names
    for pub in results:
        ntu_authors = set()
        # Authors in School: check affiliations for NTU
        authors_list = pub.get('authors_list') or pub.get('Authors List') or []
        for author in authors_list:
            name = None
            affil = None
            if isinstance(author, dict):
                name = author.get('name') or author.get('display_name') or author.get('full_name')
                affil = author.get('affiliation') or author.get('affiliations')
                # affil can be a list or string
                affil_str = ''
                if affil:
                    if isinstance(affil, list):
                        affil_str = ' '.join([str(a) for a in affil])
                    else:
                        affil_str = str(affil)
                if name and affil_str and ('ntu' in affil_str.lower() or 'nanyang technological university' in affil_str.lower()):
                    ntu_authors.add(name.strip())
            elif isinstance(author, str):
                # fallback: check if author name matches faculty_names
                if author.strip().lower() in faculty_names:
                    ntu_authors.add(author.strip())
        # fallback: string match on All Authors
        if not ntu_authors:
            authors_str = pub.get('All Authors') or pub.get('Authors') or pub.get('authors')
            if authors_str:
                tokens = [a.strip() for a in re.split(r';|,', authors_str) if a.strip()]
                for t in tokens:
                    if t.lower() in faculty_names:
                        ntu_authors.add(t)
        pub['Authors in School'] = '; '.join(ntu_authors) if ntu_authors else ''
        # Journal Title: fill if missing
        if not pub.get('Journal Title'):
            jt = pub.get('journal') or pub.get('Journal') or pub.get('container_title') or pub.get('Container Title')
            pub['Journal Title'] = jt if jt else ''
    return {'results': results}

if __name__ == '__main__':
    app.run(debug=True)
