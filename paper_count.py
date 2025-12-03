def GetCitedByCountFromOpenAlex(doi):
    import requests
    # DOI must be in the format: https://doi.org/xxx
    # OpenAlex expects: https://openalex.org/doi/DOI:xxx
    openalex_id = f"https://openalex.org/doi/DOI:{doi}"
    url = f"https://api.openalex.org/works/{openalex_id}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            return data.get("cited_by_count")
    except Exception as e:
        print(f"❌ OpenAlex error for {doi}: {e}")
    return None

def GetAuthorsFromDOI(doi):
    import requests
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            authors = []
            for a in data["message"].get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                full_name = f"{given} {family}".strip()
                if full_name:
                    authors.append(full_name)
            return authors
    except Exception as e:
        print(f"❌ CrossRef error for {doi}: {e}")
    return []

def GetAuthorsFromScienceDirect(url):
    """Extract all author names from a ScienceDirect article page using the 'author-group' tag."""
    import requests
    from bs4 import BeautifulSoup
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            print(f"❌ Error fetching ScienceDirect page: {response.status_code}")
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        author_group = soup.find("author-group")
        if not author_group:
            print("❌ 'author-group' tag not found.")
            return []
        authors = []
        for author in author_group.find_all("author"):
            name_tag = author.find("given-name")
            surname_tag = author.find("surname")
            if name_tag and surname_tag:
                full_name = f"{name_tag.text} {surname_tag.text}"
                authors.append(full_name)
        return authors
    except Exception as e:
        print(f"❌ Exception in GetAuthorsFromScienceDirect: {e}")
        return []

from requests_html import HTMLSession
from bs4 import BeautifulSoup

def GetCredentialsFromORCID(orcid_id):
    import requests
    r = requests.get(f'https://pub.orcid.org/v3.0/expanded-search/?start=0&rows=200&q=orcid:{orcid_id}', headers={"accept": "application/json"})
    try:
        return r.json()
    except Exception as e:
        print(f"❌ ORCID request failed: {e}")

def GetPublicationsByName(prof_name, start_date_str, end_date_str):
    """
    Get publications for a professor by name, searching across multiple sources:
    - Google Scholar
    - CrossRef
    - ORCID (find ORCID by name, then get publications)
    - OpenAlex
    Then deduplicate results based on DOI or title.
    """
    import requests
    import datetime
    import pandas as pd

    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')

    print(f"Searching publications for professor: {prof_name} across multiple sources")

    all_publications = []

    # Search Google Scholar
    gs_pubs = _search_google_scholar(prof_name, start_date, end_date)
    all_publications.extend(gs_pubs)

    # Search CrossRef
    cr_pubs = _search_crossref(prof_name, start_date, end_date)
    all_publications.extend(cr_pubs)

    # Search ORCID (find ORCID by name, then get publications)
    orcid_pubs = _search_orcid_by_name(prof_name, start_date, end_date)
    all_publications.extend(orcid_pubs)

    # Search OpenAlex
    oa_pubs = _search_openalex(prof_name, start_date, end_date)
    all_publications.extend(oa_pubs)

    # Deduplicate publications
    deduplicated = _deduplicate_publications(all_publications)

    # Filter to only include publications where the professor is an author.
    # Use stricter matching to avoid false positives like 'Xu Hong' vs 'Hong Xu'.
    import re
    prof_name_lower = prof_name.lower().strip()
    prof_parts = [p for p in prof_name_lower.split() if p]

    def _is_matching_publication(pub):
        # Revert to the previous 'all parts present' approach but refine for two-token names.
        # 1) If an exact full-name match exists in the authors string, accept.
        # 2) Otherwise, if all name parts appear as whole words in the authors string, accept
        #    except the special-case where the name has exactly two tokens and only the
        #    reversed-token ordering appears — in that case, require NTU affiliation.
        authors_str = (pub.get("authors") or pub.get("All Authors") or pub.get("Authors") or "")
        authors_str_l = authors_str.lower() if authors_str else ""
        if prof_name_lower and re.search(r'\b' + re.escape(prof_name_lower) + r'\b', authors_str_l):
            return True

        # Check all parts present as whole words
        parts_present = True
        for part in prof_parts:
            if not re.search(r'\b' + re.escape(part) + r'\b', authors_str_l):
                parts_present = False
                break
        if parts_present:
            # If exactly two tokens, check for reversed-only occurrence
            if len(prof_parts) == 2:
                normal = prof_name_lower
                reversed_name = f"{prof_parts[1]} {prof_parts[0]}"
                normal_present = bool(re.search(r'\b' + re.escape(normal) + r'\b', authors_str_l))
                reversed_present = bool(re.search(r'\b' + re.escape(reversed_name) + r'\b', authors_str_l))
                if reversed_present and not normal_present:
                    # require NTU affiliation for reversed-only matches; inspect authors_list
                    authors_list = pub.get('authors_list') or []
                    for a in authors_list:
                        try:
                            name = (a.get('name') or a.get('display_name') or '').lower()
                        except Exception:
                            name = ''
                        aff = ''
                        try:
                            aff = (a.get('affiliation') or a.get('raw_affiliation_string') or '')
                            aff = aff.lower() if isinstance(aff, str) else ''
                        except Exception:
                            aff = ''
                        name_tokens = [t for t in re.split(r"[;,\|\\/]+|\s+", name) if t]
                        if set(name_tokens) == set(prof_parts) and ("nanyang" in aff or "ntu" in aff or "nanyang technological university" in aff):
                            return True
                    # no NTU affiliation found for reversed-only match -> reject
                    return False
            # not the ambiguous two-token reversed case -> accept
            return True

        # As a last resort, check structured 'Authors in School' or 'Authors in School' like fields
        ais = (pub.get('Authors in School') or pub.get('authors_in_school') or '')
        if ais and prof_name_lower and re.search(r'\b' + re.escape(prof_name_lower) + r'\b', str(ais).lower()):
            return True

        return False

    filtered = [p for p in deduplicated if _is_matching_publication(p)]

    # Categorize into journal, book, chapter with standardized columns matching ORCID format
    journal_rows = []
    book_rows = []
    chapter_rows = []

    for p in filtered:
        # Get authors string
        authors_str = p.get("authors") or p.get("All Authors") or p.get("Authors")

        # Populate Authors in School
        if p.get("source") == "ORCID":
            authors_in_school_str = p.get("Authors in School")
        else:
            authors_in_school = []
            
            # Always include the professor we're searching for first
            authors_in_school.append(prof_name)
            
            # Then check other authors for NTU affiliation
            authors_list = p.get("authors_list", [])
            for author in authors_list:
                author_name = author.get("name", "")
                # Skip if this is the same as the professor we're searching for
                if author_name and author_name.lower().strip() == prof_name.lower().strip():
                    continue
                    
                aff = author.get("affiliation", "")
                # Convert affiliation to string and check for NTU
                if isinstance(aff, list):
                    aff_str = ' '.join([str(a) for a in aff])
                else:
                    aff_str = str(aff) if aff else ""
                
                # Check if author is from NTU by affiliation
                if aff_str and 'nanyang technological university' in aff_str.lower():
                    if author_name and author_name not in authors_in_school:
                        authors_in_school.append(author_name)
            
            authors_in_school_str = "; ".join(authors_in_school) if authors_in_school else None

        if p.get('type') == 'journal':
            journal_rows.append({
                "All Authors": authors_str,
                "Authors in School": authors_in_school_str,
                "Article Title": p.get("title"),
                "Article DOI": p.get("doi"),
                "Year": p.get("year"),
                "Journal Title": p.get("Journal Title"),
                "Publication Date": str(p.get("year")) if p.get("year") else None,
                "Citation Count": p.get("citation_count"),
                "source": p.get("source")
            })
        elif p.get('type') == 'book':
            book_rows.append({
                "Authors": authors_str,
                "Authors in School": authors_in_school_str,
                "Book Title": p.get("title"),
                "Year": p.get("year"),
                "Publisher": p.get("Publisher"),  # Extract from ORCID if available
                "Citation Count": p.get("citation_count"),
                "Publication Date": str(p.get("year")) if p.get("year") else None,
                "source": p.get("source")
            })
        elif p.get('type') == 'chapter':
            chapter_rows.append({
                "Authors": authors_str,
                "Authors in School": authors_in_school_str,
                "Book Title": p.get("Book Title"),  # Extract from ORCID if available
                "Chapter Title": p.get("title"),
                "Year": p.get("year"),
                "Publisher": p.get("Publisher"),  # Extract from ORCID if available
                "Citation Count": p.get("citation_count"),
                "Publication Date": str(p.get("year")) if p.get("year") else None,
                "source": p.get("source")
            })
    # Normalize, deduplicate and sort results (newest first)
    from statistics import mean

    def _normalize_row(p, kind='journal'):
        r = dict(p)
        # DOI
        doi = r.get('Article DOI') or r.get('doi') or r.get('DOI')
        if doi:
            doi = str(doi).strip()
            doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
            r['Article DOI'] = doi
        else:
            r['Article DOI'] = None

        # Title
        title = r.get('Article Title') or r.get('title') or r.get('Chapter Title') or r.get('Book Title')
        r['Article Title'] = title

        # Authors
        authors = r.get('All Authors') or r.get('Authors') or r.get('authors')
        if not authors:
            a_list = r.get('authors_list') or []
            names = []
            try:
                for a in a_list:
                    if isinstance(a, dict):
                        n = a.get('name') or a.get('full_name')
                        if n:
                            names.append(str(n).strip())
                    elif isinstance(a, str):
                        names.append(a.strip())
            except Exception:
                pass
            if names:
                authors = '; '.join(dict.fromkeys(names))
        if authors and isinstance(authors, str):
            authors = authors.replace(', ', '; ')
        r['All Authors'] = authors

        # Journal Title normalization
        journal_title = r.get('Journal Title') or r.get('journal_title') or r.get('container_title') or r.get('Journal')
        r['Journal Title'] = journal_title if journal_title else None

        # Citation count - collect possible keys
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
        r['Citation Count'] = int(round(mean(counts))) if counts else (int(r.get('Citation Count') or 0) if r.get('Citation Count') is not None else 0)

        # Publication Date normalization - preserve original format if it's already properly formatted
        pub_raw = r.get('Publication Date') or r.get('publication_date') or r.get('Year') or r.get('year')
        if pub_raw:
            pub_raw_str = str(pub_raw).strip()
            # If it's already in YYYY, YYYY-MM, or YYYY-MM-DD format (with or without zero-padding), keep it as-is
            import re
            date_pattern = re.compile(r'^\d{4}(-\d{1,2})?(-\d{1,2})?$')
            if date_pattern.match(pub_raw_str):
                r['Publication Date'] = pub_raw_str
            else:
                # Try to parse and normalize other formats
                pub_dt = None
                try:
                    pub_dt = pd.to_datetime(pub_raw, errors='coerce')
                except Exception:
                    pub_dt = None
                if pub_dt is not None and not pd.isna(pub_dt):
                    try:
                        r['Publication Date'] = pub_dt.strftime('%Y-%m-%d')
                    except Exception:
                        r['Publication Date'] = str(pub_dt)
                else:
                    try:
                        y = int(str(pub_raw_str)[:4])
                        r['Publication Date'] = str(y)
                    except Exception:
                        r['Publication Date'] = None
        else:
            r['Publication Date'] = None

        return r

    def _dedupe_and_sort(rows):
        keyed = {}
        # Source priority: ORCID > Google Scholar > CrossRef > OpenAlex > Unknown
        source_priority = {"ORCID": 0, "Google Scholar": 1, "CrossRef": 2, "OpenAlex": 3, "Unknown": 4}
        
        for p in rows:
            r = _normalize_row(p)
            if r.get('Article DOI'):
                key = ('doi', r.get('Article DOI').lower())
            else:
                t = r.get('Article Title') or ''
                key = ('title', str(t).strip().lower())

            if key in keyed:
                existing = keyed[key]
                # Prioritize source: if new source has higher priority, update the source
                new_source = r.get('source', 'Unknown')
                existing_source = existing.get('source', 'Unknown')
                new_priority = source_priority.get(new_source, 4)
                existing_priority = source_priority.get(existing_source, 4)
                if new_priority < existing_priority:
                    existing['source'] = new_source
                
                # merge citation counts list
                existing_counts = existing.get('_merged_counts', [])
                existing_counts.append(r.get('Citation Count') or 0)
                existing['_merged_counts'] = existing_counts
                # merge authors
                a1 = existing.get('All Authors') or ''
                a2 = r.get('All Authors') or ''
                merged = []
                for s in (a1, a2):
                    if s:
                        for name in [n.strip() for n in s.split(';') if n.strip()]:
                            if name not in merged:
                                merged.append(name)
                if merged:
                    existing['All Authors'] = '; '.join(merged)
                # take latest publication date
                try:
                    d1 = pd.to_datetime(existing.get('Publication Date'), errors='coerce')
                    d2 = pd.to_datetime(r.get('Publication Date'), errors='coerce')
                    if d2 is not None and not pd.isna(d2) and (d1 is None or pd.isna(d1) or d2 > d1):
                        existing['Publication Date'] = r.get('Publication Date')
                except Exception:
                    pass
                # preserve Journal Title if existing doesn't have it but new row does
                if not existing.get('Journal Title') and r.get('Journal Title'):
                    existing['Journal Title'] = r.get('Journal Title')
            else:
                new = dict(r)
                new['_merged_counts'] = [new.get('Citation Count') or 0]
                keyed[key] = new

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

        # sort by publication date descending
        try:
            out.sort(key=lambda r: pd.to_datetime(r.get('Publication Date'), errors='coerce') or pd.Timestamp(0), reverse=True)
        except Exception:
            pass
        return out

    # Apply dedupe/sort
    journal_rows = _dedupe_and_sort(journal_rows)
    book_rows = _dedupe_and_sort(book_rows)
    chapter_rows = _dedupe_and_sort(chapter_rows)

    # Print results
    if journal_rows:
        print(f"\nJournal Articles for {prof_name}:")
        print(pd.DataFrame(journal_rows))
    if book_rows:
        print(f"\nBooks for {prof_name}:")
        print(pd.DataFrame(book_rows))
    if chapter_rows:
        print(f"\nBook Chapters for {prof_name}:")
        print(pd.DataFrame(chapter_rows))

    return {"journal": journal_rows, "book": book_rows, "chapter": chapter_rows}

def _search_google_scholar(prof_name, start_date, end_date):
    """Search Google Scholar for publications by professor name."""
    # Placeholder implementation - Google Scholar scraping is complex and may violate terms
    # In a real implementation, you might use scholarly library or similar
    print("Google Scholar search not implemented (requires scraping or API)")
    return []

def _search_crossref(prof_name, start_date, end_date):
    """Search CrossRef for publications by professor name."""
    import requests
    import datetime

    url = f"https://api.crossref.org/works?query.author={prof_name}&rows=100"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            pubs = []
            for item in data.get("message", {}).get("items", []):
                title = item.get("title", ["Untitled"])[0]
                date_parts = item.get("published-print", {}).get("date-parts", [[None]])[0]
                if not date_parts or not date_parts[0]:
                    continue
                pub_year = date_parts[0]
                pub_date_obj = datetime.datetime(pub_year, 1, 1)
                if not (start_date <= pub_date_obj <= end_date):
                    continue
                # Extract full date with month and day if available
                pub_date_str = str(pub_year)
                if len(date_parts) > 1 and date_parts[1]:
                    pub_date_str = f"{pub_year}-{date_parts[1]:02d}"
                    if len(date_parts) > 2 and date_parts[2]:
                        pub_date_str = f"{pub_year}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                doi = item.get("DOI")
                authors_list = []
                for author in item.get("author", []):
                    full_name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                    if full_name:
                        aff = author.get("affiliation", [])
                        aff_str = "; ".join([a.get("name", "") for a in aff if a.get("name")])
                        authors_list.append({"name": full_name, "affiliation": aff_str})
                authors_str = ", ".join([a["name"] for a in authors_list]) if authors_list else None
                citation_count = GetCitedByCountFromOpenAlex(doi) if doi else item.get("is-referenced-by-count", 0)
                journal_title = item.get('container-title', [])
                journal_title = journal_title[0] if isinstance(journal_title, list) and journal_title else (item.get('publisher') or None)
                pubs.append({
                    "type": "journal",  # Assuming most CrossRef works are journal articles
                    "title": title,
                    "doi": doi,
                    "year": pub_year,
                    "Publication Date": pub_date_str,
                    "authors": authors_str,
                    "authors_list": authors_list,
                    "citation_count": citation_count,
                    "Journal Title": journal_title,
                    "source": "CrossRef"
                })
            return pubs
    except Exception as e:
        print(f"❌ CrossRef search error: {e}")
    return []

def _search_orcid_by_name(prof_name, start_date, end_date):
    """Find ORCID by name, then get publications."""
    import requests
    import re

    # Search for ORCID by name with stricter matching
    search_url = f"https://pub.orcid.org/v3.0/expanded-search/?q={prof_name}&rows=50"
    try:
        r = requests.get(search_url, headers={"accept": "application/json"})
        if r.status_code == 200:
            data = r.json()
            results = data.get("expanded-result", [])
            # Filter results using the previous permissive rule: accept exact full-name match
            # or if all parts appear in the ORCID record's full name.
            filtered_results = []
            prof_name_lower = prof_name.lower().strip()
            prof_parts = [p for p in prof_name_lower.split() if p]
            for result in results:
                given_names = result.get("given-names", "").lower().strip()
                family_name = result.get("family-name", "").lower().strip()
                full_name = f"{given_names} {family_name}".strip()
                # Exact match or if all parts of prof_name are in full_name
                if prof_name_lower == full_name or all(part in full_name for part in prof_parts):
                    filtered_results.append(result)
            if filtered_results:
                # Take the first filtered result
                orcid_id = filtered_results[0].get("orcid-id")
                if orcid_id:
                    print(f"Found ORCID {orcid_id} for {prof_name}")
                    # Get publications from ORCID
                    pubs = _get_publications_from_orcid(orcid_id, start_date, end_date)
                    # Convert to list format
                    all_pubs = []
                    for pub_type, pub_list in pubs.items():
                        for pub in pub_list:
                            pub["type"] = pub_type
                            pub["source"] = "ORCID"
                            all_pubs.append(pub)
                    return all_pubs
    except Exception as e:
        print(f"❌ ORCID search error: {e}")
    return []

def _search_openalex(prof_name, start_date, end_date):
    """Search OpenAlex for publications by professor name."""
    import requests
    import datetime

    # First, find author ID
    author_search_url = f"https://api.openalex.org/authors?search={prof_name}&per-page=10"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AcademicResearchTool/1.0)"}
    try:
        r = requests.get(author_search_url, headers=headers)
        if r.status_code == 200:
            author_data = r.json()
            authors = author_data.get("results", [])
            if authors:
                author_id = authors[0]["id"]
                # Get works
                works_url = f"https://api.openalex.org/works?filter=author.id:{author_id.split('/')[-1]}&per_page=200"
                r = requests.get(works_url)
                if r.status_code == 200:
                    works_data = r.json()
                    works = works_data.get("results", [])
                    pubs = []
                    for work in works:
                        title = work.get("title", "Untitled")
                        publication_year = work.get("publication_year")
                        if not publication_year:
                            continue
                        pub_date_obj = datetime.datetime(publication_year, 1, 1)
                        if not (start_date <= pub_date_obj <= end_date):
                            continue
                        doi = work.get("doi")
                        if doi:
                            doi = doi.replace("https://doi.org/", "")
                        authors_list = []
                        for authorship in work.get("authorships", []):
                            author_name = authorship.get("author", {}).get("display_name", "")
                            aff = authorship.get("raw_affiliation_string", "")
                            if author_name:
                                authors_list.append({"name": author_name, "affiliation": aff})
                        authors_str = ", ".join([a["name"] for a in authors_list]) if authors_list else None
                        work_type = work.get("type", "")
                        citation_count = work.get("cited_by_count", 0)
                        pub_type = "journal" if work_type in ["article", "journal-article"] else "book" if work_type == "book" else "chapter"
                        # Extract journal title from multiple possible fields
                        journal_title = None
                        primary_location = work.get('primary_location') or {}
                        source = primary_location.get('source') or {}
                        journal_title = source.get('display_name')
                        # Fallback to legacy host_venue if primary_location not available
                        if not journal_title:
                            host = work.get('host_venue') or {}
                            journal_title = host.get('display_name') or host.get('publisher')
                        # Extract publication date with month and day if available
                        pub_date_str = work.get('publication_date') or None
                        if not pub_date_str:
                            pub_date_str = str(publication_year)
                        pubs.append({
                            "type": pub_type,
                            "title": title,
                            "doi": doi,
                            "year": publication_year,
                            "Publication Date": pub_date_str,
                            "authors": authors_str,
                            "authors_list": authors_list,
                            "citation_count": citation_count,
                            "Journal Title": journal_title,
                            "source": "OpenAlex"
                        })
                    return pubs
    except Exception as e:
        print(f"❌ OpenAlex search error: {e}")
    return []

def _deduplicate_publications(publications):
    """Deduplicate publications based on DOI or title similarity."""
    seen_dois = set()
    seen_titles = set()
    deduplicated = []
    for pub in publications:
        doi = pub.get("doi")
        title = pub.get("title", "").lower().strip()
        if doi and doi not in seen_dois:
            seen_dois.add(doi)
            deduplicated.append(pub)
        elif not doi and title not in seen_titles:
            seen_titles.add(title)
            deduplicated.append(pub)
    return deduplicated



def LoadFacultyJoinYears(excel_source, sheet_name='Worker Listing as of 30 Sep', header=2):
    """Load faculty join dates from an Excel file (path or bytes).

    Returns two dicts: by_orcid and by_name. Each maps to {'join_year': int|None, 'join_month': int|None}.

    excel_source can be a filesystem path or bytes (file contents).
    """
    import pandas as pd
    import io

    try:
        if isinstance(excel_source, (bytes, bytearray)):
            df = pd.read_excel(io.BytesIO(excel_source), sheet_name=sheet_name, header=header)
        else:
            df = pd.read_excel(excel_source, sheet_name=sheet_name, header=header)
    except Exception:
        # fallback: try reading without header
        try:
            if isinstance(excel_source, (bytes, bytearray)):
                df = pd.read_excel(io.BytesIO(excel_source), sheet_name=sheet_name)
            else:
                df = pd.read_excel(excel_source, sheet_name=sheet_name)
        except Exception as e:
            print(f"❌ Failed to load faculty sheet: {e}")
            return {}, {}, None

    # Normalize column names
    cols = {str(c).strip(): c for c in df.columns}
    # Prefer 'Join Date' then 'Join Year'
    join_col = None
    for c in ['Join Date', 'Join Year', 'Join', 'join date', 'join_year', 'JoinDate']:
        if c in cols:
            join_col = cols[c]
            break

    # Standardize date/year parsing
    if join_col is not None:
        try:
            if 'year' in str(join_col).lower() and pd.api.types.is_numeric_dtype(df[join_col]):
                df['Join Year'] = df[join_col].astype('Int64')
                df['Join Month'] = None
            else:
                df['Join Date'] = pd.to_datetime(df[join_col], errors='coerce')
                df['Join Year'] = df['Join Date'].dt.year
                df['Join Month'] = df['Join Date'].dt.month
        except Exception:
            df['Join Year'] = None
            df['Join Month'] = None
    else:
        df['Join Year'] = None
        df['Join Month'] = None

    # Find ORCID and Name columns
    orcid_col = None
    name_col = None
    for c in df.columns:
        low = str(c).lower()
        if 'orcid' in low:
            orcid_col = c
        if any(k in low for k in ['name', 'full name', 'employee']):
            name_col = c

    by_orcid = {}
    by_name = {}
    # Iterate all rows (including row 0) to capture all faculty
    for idx, row in df.iterrows():
        orcid = None
        name = None
        try:
            if orcid_col and not pd.isna(row.get(orcid_col)):
                orcid = str(row.get(orcid_col)).strip()
        except Exception:
            orcid = None
        try:
            if name_col and not pd.isna(row.get(name_col)):
                name = str(row.get(name_col)).strip()
        except Exception:
            name = None

        jy = None
        jm = None
        try:
            v = row.get('Join Year')
            if not pd.isna(v):
                jy = int(v)
        except Exception:
            jy = None
        try:
            v2 = row.get('Join Month')
            if not pd.isna(v2):
                jm = int(v2)
        except Exception:
            jm = None

        if orcid:
            by_orcid[orcid] = {'join_year': jy, 'join_month': jm}
        if name:
            by_name[name.strip().lower()] = {'join_year': jy, 'join_month': jm}

    # Also return a compact DataFrame for inspection
    try:
        df_faculty_info = df[['Name', 'ORCID ID', 'Join Year', 'Join Month']].copy()
    except Exception:
        df_faculty_info = df

    return by_orcid, by_name, df_faculty_info

def GetPublicationsFromORCID(orcid_id, from_date, to_date):
    """Get publications from ORCID API for a given ORCID ID between from_date and to_date."""
    return _get_publications_from_orcid(orcid_id, from_date, to_date)

def _get_publications_from_orcid(orcid_id, from_date, to_date):
    """Helper function to get publications from ORCID API."""
    import requests
    import datetime

    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {"accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"❌ ORCID API error: {r.status_code}")
        return {"journal": [], "book": [], "chapter": []}
    try:
        import pandas as pd
        data = r.json()
        journal_rows, book_rows, chapter_rows = [], [], []
        for group in data.get("group", []):
            work_summaries = group.get("work-summary", None)
            if not work_summaries or not isinstance(work_summaries, list):
                continue
            if len(work_summaries) == 0 or not isinstance(work_summaries[0], dict):
                continue
            summary = work_summaries[0]
            title = summary.get("title", {}).get("title", {}).get("value", "Untitled")
            doi = None
            for ext_id in summary.get("external-ids", {}).get("external-id", []):
                if ext_id.get("external-id-type") == "doi":
                    doi = ext_id.get("external-id-value")
                    break
            pub_date_info = summary.get("publication-date")
            pub_year = pub_month = pub_day = None
            if pub_date_info:
                year_field = pub_date_info.get("year")
                month_field = pub_date_info.get("month")
                day_field = pub_date_info.get("day")
                pub_year = year_field.get("value", None) if isinstance(year_field, dict) else None
                pub_month = month_field.get("value", None) if isinstance(month_field, dict) else None
                pub_day = day_field.get("value", None) if isinstance(day_field, dict) else None
            pub_date = None
            if pub_year:
                # Build date string with ACTUAL available parts (for display)
                date_parts = [pub_year]
                if pub_month:
                    date_parts.append(f"{int(pub_month):02d}")
                    if pub_day:
                        date_parts.append(f"{int(pub_day):02d}")
                pub_date = "-".join(date_parts)
                
                # Filter by year only (simpler and more reliable)
                try:
                    filter_year = int(pub_year)
                    from_year = from_date.year
                    to_year = to_date.year
                    
                    # Check if publication year falls within the search year range
                    if not (from_year <= filter_year <= to_year):
                        continue
                except Exception:
                    continue
            else:
                continue  # Skip if no year

            journal_title = summary.get("journal-title", {}).get("value") if summary.get("journal-title") else None
            type_of_work = summary.get("type", "")
            # --- Robust fallback for Book/Chapter fields ---
            # Book Title for chapters: try summary, then group, then all summaries
            book_title = None
            if type_of_work == "book-chapter":
                book_title = summary.get("container-title", {}).get("value") if summary.get("container-title") else None
                if not book_title and "title" in group:
                    book_title = group["title"].get("title", {}).get("value")
                if not book_title:
                    for ws in work_summaries:
                        bt = ws.get("container-title", {}).get("value") if ws.get("container-title") else None
                        if bt:
                            book_title = bt
                            break
            # Publisher: try summary, then group, then all summaries
            publisher = summary.get("publisher", {}).get("value") if summary.get("publisher") else None
            if not publisher and "publisher" in group:
                publisher = group["publisher"].get("value")
            if not publisher:
                for ws in work_summaries:
                    pub = ws.get("publisher", {}).get("value") if ws.get("publisher") else None
                    if pub:
                        publisher = pub
                        break
            # Citation count: use OpenAlex cited_by_count if DOI exists
            citation_count = None
            if doi:
                citation_count = GetCitedByCountFromOpenAlex(doi)
            else:
                # Try ISBN for books/chapters
                isbn = None
                for ext_id in summary.get("external-ids", {}).get("external-id", []):
                    if ext_id.get("external-id-type") == "isbn":
                        isbn = ext_id.get("external-id-value")
                        break
                if isbn:
                    citation_count = None  # Placeholder
            # If still None after all attempts, set to 0 to avoid NaN
            if citation_count is None:
                citation_count = 0
            # Authors
            authors = []
            contributors = summary.get("contributors", {}).get("contributor", []) if summary.get("contributors") else []
            for c in contributors:
                name = c.get("credit-name", {}).get("value")
                if not name:
                    orcid_obj = c.get("contributor-orcid", {}).get("path")
                    if orcid_obj:
                        name = orcid_obj
                if name:
                    authors.append(name)
            authors_str = ", ".join(authors) if authors else None
            if not authors_str:
                try:
                    cred = GetCredentialsFromORCID(orcid_id)
                    if cred and 'expanded-result' in cred and len(cred['expanded-result']) > 0:
                        profile_name = cred['expanded-result'][0].get('given-names', '') + ' ' + cred['expanded-result'][0].get('family-name', '')
                        authors_str = profile_name.strip() if profile_name.strip() else None
                except Exception:
                    pass
            if type_of_work == "journal-article":
                # Try CrossRef DOI lookup for all authors first
                all_authors = []
                if doi:
                    doi_authors = GetAuthorsFromDOI(doi)
                    if doi_authors:
                        all_authors = doi_authors
                    else:
                        print(f"CrossRef DOI lookup failed for {doi}, falling back to ORCID contributors")
                # If DOI lookup fails, fallback to ORCID contributors
                if not all_authors:
                    # From all work summaries
                    for ws in work_summaries:
                        ws_contributors = ws.get("contributors", {}).get("contributor", [])
                        for c in ws_contributors:
                            name = c.get("credit-name", {}).get("value")
                            if not name:
                                orcid_obj = c.get("contributor-orcid", {}).get("path")
                                if orcid_obj:
                                    name = orcid_obj
                            if name:
                                all_authors.append(name)
                    # From group-level contributors
                    if group.get("contributors"):
                        for c in group["contributors"].get("contributor", []):
                            name = c.get("credit-name", {}).get("value")
                            if not name:
                                orcid_obj = c.get("contributor-orcid", {}).get("path")
                                if orcid_obj:
                                    name = orcid_obj
                            if name:
                                all_authors.append(name)
                    # Deduplicate authors (preserve order)
                    all_authors = list(dict.fromkeys(all_authors))
                all_authors_str = ", ".join(all_authors) if all_authors else None
                
                # Build authors_list for affiliation checking
                authors_list = []
                if doi:
                    # Try to get detailed author info from CrossRef
                    try:
                        r_crossref = requests.get(f"https://api.crossref.org/works/{doi}")
                        if r_crossref.status_code == 200:
                            cr_data = r_crossref.json()
                            for cr_author in cr_data.get("message", {}).get("author", []):
                                full_name = f"{cr_author.get('given', '')} {cr_author.get('family', '')}".strip()
                                if full_name:
                                    aff = cr_author.get("affiliation", [])
                                    aff_str = "; ".join([a.get("name", "") for a in aff if a.get("name")])
                                    authors_list.append({"name": full_name, "affiliation": aff_str})
                    except Exception:
                        pass
                
                # Fallback: build minimal authors_list from all_authors
                if not authors_list and all_authors:
                    authors_list = [{"name": name, "affiliation": ""} for name in all_authors]
                
                journal_rows.append({
                    "All Authors": all_authors_str,
                    "authors": all_authors_str,
                    "authors_list": authors_list,
                    "Authors in School": authors_str,
                    "Article Title": title,
                    "title": title,
                    "Article DOI": doi,
                    "doi": doi,
                    "Year": pub_year,
                    "year": pub_year,
                    "Journal Title": journal_title,
                    "Publication Date": pub_date,
                    "Citation Count": citation_count,
                    "citation_count": citation_count
                })
            elif type_of_work == "book":
                # Try to get publisher from CrossRef if DOI exists
                crossref_publisher = None
                if doi:
                    try:
                        r = requests.get(f"https://api.crossref.org/works/{doi}")
                        if r.status_code == 200:
                            data = r.json()
                            crossref_publisher = data["message"].get("publisher")
                    except Exception as e:
                        print(f"❌ CrossRef publisher error for {doi}: {e}")
                final_publisher = crossref_publisher if crossref_publisher else publisher
                # --- Publisher fallback ---
                if not final_publisher:
                    # Try OpenAlex if DOI exists
                    if doi:
                        try:
                            r = requests.get(f"https://api.openalex.org/works/https://doi.org/{doi}")
                            if r.status_code == 200:
                                data = r.json()
                                final_publisher = data.get("host_venue", {}).get("publisher")
                        except Exception:
                            pass
                    # Fallback to journal-title/container-title if available
                    if not final_publisher:
                        final_publisher = journal_title or book_title
                # --- Citation Count fallback ---
                if citation_count is None and doi:
                    citation_count = GetCitationCountFromSemanticScholar(doi)
                if citation_count is None and not doi:
                    try:
                        r = requests.get(f"https://api.openalex.org/works?filter=title.search:{title}")
                        if r.status_code == 200:
                            results = r.json().get("results", [])
                            if results:
                                citation_count = results[0].get("cited_by_count")
                    except Exception:
                        pass
                # If still None after all attempts, set to 0 to avoid NaN
                if citation_count is None:
                    citation_count = 0
                book_rows.append({
                    "Authors": authors_str,
                    "authors": authors_str,
                    "Book Title": title,
                    "title": title,
                    "Year": pub_year,
                    "year": pub_year,
                    "Publisher": final_publisher,
                    "Citation Count": citation_count,
                    "citation_count": citation_count,
                    "Publication Date": pub_date
                })
            elif type_of_work == "book-chapter":
                # Try to get publisher from CrossRef if DOI exists
                crossref_publisher = None
                if doi:
                    try:
                        r = requests.get(f"https://api.crossref.org/works/{doi}")
                        if r.status_code == 200:
                            data = r.json()
                            crossref_publisher = data["message"].get("publisher")
                    except Exception as e:
                        print(f"❌ CrossRef publisher error for {doi}: {e}")
                final_publisher = crossref_publisher if crossref_publisher else publisher
                # --- Publisher fallback ---
                if not final_publisher:
                    # Try OpenAlex if DOI exists
                    if doi:
                        try:
                            r = requests.get(f"https://api.openalex.org/works/https://doi.org/{doi}")
                            if r.status_code == 200:
                                data = r.json()
                                final_publisher = data.get("host_venue", {}).get("publisher")
                        except Exception:
                            pass
                    # Fallback to journal-title/container-title if available
                    if not final_publisher:
                        final_publisher = journal_title or book_title
                # --- Citation Count fallback ---
                if citation_count is None and doi:
                    citation_count = GetCitationCountFromSemanticScholar(doi)
                if citation_count is None and not doi:
                    try:
                        r = requests.get(f"https://api.openalex.org/works?filter=title.search:{title}")
                        if r.status_code == 200:
                            results = r.json().get("results", [])
                            if results:
                                citation_count = results[0].get("cited_by_count")
                    except Exception:
                        pass
                chapter_title = title
                chapter_rows.append({
                    "Authors": authors_str,
                    "authors": authors_str,
                    "Book Title": book_title,
                    "Chapter Title": chapter_title,
                    "title": chapter_title,
                    "Year": pub_year,
                    "year": pub_year,
                    "Publisher": final_publisher,
                    "Citation Count": citation_count,
                    "citation_count": citation_count,
                    "Publication Date": pub_date
                })
        # Print DataFrames
        if not journal_rows:
            print("No journal articles found for this ORCID in the given years.")
        else:
            print("\nJournal Articles:")
            print(pd.DataFrame(journal_rows))
        if not book_rows:
            print("No books found for this ORCID in the given years.")
        else:
            print("\nBooks:")
            print(pd.DataFrame(book_rows))
        if not chapter_rows:
            print("No book chapters found for this ORCID in the given years.")
        else:
            print("\nBook Chapters:")
            print(pd.DataFrame(chapter_rows))
        # Return all for further use if needed
        return {"journal": journal_rows, "book": book_rows, "chapter": chapter_rows}
    except Exception as e:
        print(f"Error in _get_publications_from_orcid: {e}")
        return {"journal": [], "book": [], "chapter": []}

def GetCitationCountFromSemanticScholar(doi):
    import requests
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=citationCount"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            return data.get("citationCount")
    except Exception:
        pass
    return None
