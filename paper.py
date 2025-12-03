from scholarly import scholarly
from datetime import datetime
import re
import time
import pandas as pd
import os


def parse_date(date_str):
    """Convert dd-mm-yyyy to year."""
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").year
    except Exception as e:
        print(f"⚠️ Invalid date format: {e}")
        return None


def extract_user_id(scholar_url):
    """Extract 'user' parameter from Google Scholar URL."""
    match = re.search(r"user=([\w-]+)", scholar_url)
    return match.group(1) if match else None


def get_author_from_scholar_url(url):
    """Get author using Google Scholar profile URL."""
    user_id = extract_user_id(url)
    if not user_id:
        print("❌ Couldn't extract user ID from the Scholar URL.")
        return None
    try:
        return scholarly.search_author_id(user_id)
    except Exception as e:
        print(f"❌ Error fetching author: {e}")
        return None


def get_author_by_name(name, university):
    """Fallback search by name and university."""
    search_query = scholarly.search_author(name)
    for author in search_query:
        affiliation = author.get("affiliation", "").lower()
        if university.lower() in affiliation:
            return author
    return None


def get_publications(author, university, start_year, end_year):
    """Return publications with type and year info for filtering/categorization."""
    try:
        filled = scholarly.fill(author)
        pubs = filled.get("publications", [])
        results = []
        for pub in pubs:
            try:
                detailed = scholarly.fill(pub)
                bib = detailed.get("bib", {})
                pub_year = int(bib.get("pub_year", 0))
                title = bib.get("title", "Untitled")
                # Try to infer type from bib fields
                venue = bib.get("venue", "").lower()
                pub_type = "Other"
                if "journal" in venue:
                    pub_type = "Journal"
                elif "conference" in venue or "symposium" in venue or "proceedings" in venue:
                    pub_type = "Conference"
                elif "book chapter" in venue or "chapter" in venue:
                    pub_type = "Book Chapter"
                elif "book" in venue:
                    pub_type = "Book"
                results.append({
                    "title": title,
                    "year": pub_year,
                    "type": pub_type,
                    "venue": bib.get("venue", ""),
                })
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"⚠️ Error retrieving publications: {e}")
        return []

import requests

def get_publications_from_orcid(orcid_id, start_year, end_year):
    headers = {"Accept": "application/json"}
    # Accept both full URL and just the ID
    if orcid_id.startswith("http"):
        orcid_id = orcid_id.rstrip("/").split("/")[-1]
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ ORCID API error: {response.status_code}")
            return []
        data = response.json()
        results = []
        for work in data.get("group", []):
            summary = work.get("work-summary", [])[0]
            title = summary.get("title", {}).get("title", {}).get("value", "Untitled")
            pub_year = summary.get("publication-date", {}).get("year", {}).get("value", None)
            venue = summary.get("journal-title", {}).get("value", "").lower()
            pub_type = "Other"
            if "journal" in venue:
                pub_type = "Journal"
            elif "conference" in venue or "symposium" in venue or "proceedings" in venue:
                pub_type = "Conference"
            elif "book chapter" in venue or "chapter" in venue:
                pub_type = "Book Chapter"
            elif "book" in venue:
                pub_type = "Book"
            if pub_year:
                try:
                    pub_year = int(pub_year)
                    if start_year <= pub_year <= end_year:
                        results.append({
                            "title": title,
                            "year": pub_year,
                            "type": pub_type,
                            "venue": venue,
                        })
                except:
                    continue
        return results
    except Exception as e:
        print(f"⚠️ ORCID request failed: {e}")
        return []



def main():
    print("\n📚 SSS Faculty Publication Extractor (2019-2024)\n")
    # Read input file (Excel) from current folder
    input_file = "input source _Faculty cv.xlsx"
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    df_in = pd.read_excel(input_file)

    all_results = []
    for idx, row in df_in.iterrows():
        name = row.get('Name', '').strip()
        id_type = str(row.get('ID Type', '')).strip().lower()
        id_value = str(row.get('ID', '')).strip()
    date_joined = row.get('NTU Join Date', '')
        date_left = row.get('Date Left', '')
        # Use pandas to_datetime for robust parsing
        try:
            joined_dt = pd.to_datetime(date_joined, errors='coerce')
        except Exception:
            joined_dt = None
        if pd.isnull(joined_dt):
            print(f"⚠️ Skipping {name}: Invalid or missing NTU Join Date ('{date_joined}')")
            continue
        joined_year = joined_dt.year
        if date_left:
            try:
                left_dt = pd.to_datetime(date_left, errors='coerce')
            except Exception:
                left_dt = None
            left_year = left_dt.year if left_dt is not None and not pd.isnull(left_dt) else 2024
        else:
            left_year = 2024
        start_year = max(2019, joined_year)
        end_year = min(2024, left_year)
        pubs = []
        if id_type == "orcid":
            pubs = get_publications_from_orcid(id_value, start_year, end_year)
        elif id_type == "scholar":
            author = get_author_from_scholar_url(f"https://scholar.google.com/citations?user={id_value}")
            if author:
                pubs = get_publications(author, None, start_year, end_year)
            else:
                print(f"❌ Unable to fetch author from Google Scholar for {name}.")
        else:
            print(f"❌ Invalid ID type for {name}. Use 'orcid' or 'scholar'.")
        categories = {"Journal": [], "Book": [], "Book Chapter": [], "Conference": []}
        for pub in pubs:
            cat = pub["type"]
            if cat in categories:
                categories[cat].append(pub["title"])
        all_results.append({
            "Name": name,
            "Journal": ", ".join(categories["Journal"]),
            "Book": ", ".join(categories["Book"]),
            "Book Chapter": ", ".join(categories["Book Chapter"]),
            "Conference": ", ".join(categories["Conference"]),
        })

    df_out = pd.DataFrame(all_results)
    print("\nResults:")
    print(df_out)


if __name__ == "__main__":
    main()




from requests_html import HTMLSession
from bs4 import BeautifulSoup

def GetCredentialsFromORCID(orcid_id):
    
    import requests

    r = requests.get(f'https://pub.orcid.org/v3.0/expanded-search/?start=0&rows=200&q=orcid:{orcid_id}', headers={"accept": "application/json"})
    try:
        return r.json()
    except Exception as e:
        print(f"❌ ORCID request failed: {e}")
        

def GetPublicationsFromORCID(orcid_id, start_year, end_year):
    import requests
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {"accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"❌ ORCID API error: {r.status_code}")
        return []
    try:
        data = r.json()
        results = []
        for group in data.get("group", []):
            summary = group.get("work-summary", [])[0]
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
                try:
                    pub_year_int = int(pub_year)
                    if start_year <= pub_year_int <= end_year:
                        # Build date string with available parts
                        date_parts = [pub_year]
                        if pub_month:
                            date_parts.append(pub_month)
                        if pub_day:
                            date_parts.append(pub_day)
                        pub_date = "-".join(date_parts)
                        # Journal, Book, Chapter info
                        journal_title = summary.get("journal-title", {}).get("value")
                        type_of_work = summary.get("type", "")
                        book_title = None
                        chapter_title = None
                        if type_of_work == "book":
                            book_title = title
                        elif type_of_work == "book-chapter":
                            chapter_title = title
                            # Try to get book title from group
                            book_title = group.get("work-summary", [{}])[0].get("container-title", {}).get("value")
                        # Citation count from Semantic Scholar
                        citation_count = None
                        if doi:
                            citation_count = GetCitationCountFromSemanticScholar(doi)
                        results.append({
                            "title": title,
                            "doi": doi,
                            "journal_title": journal_title,
                            "book_title": book_title,
                            "chapter_title": chapter_title,
                            "citation_count": citation_count,
                            "publication_date": pub_date,
                            "type": type_of_work
                        })
                except Exception:
                    continue
        return results
    except Exception as e:
        print(f"Error in GetPublicationsFromORCID: {e}")
        return []
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
    return results

# Example usage
orcid_id = "0000-0003-1389-5408"  # Replace with a valid ORCID ID
start_year = 2019
end_year = 2024
publications = GetPublicationsFromORCID(orcid_id, start_year, end_year)
for pub in publications:
    print("\n---")
    print(f"Title: {pub['title']}")
    print(f"DOI: {pub['doi']}")
    if pub['type'] == 'journal-article':
        print(f"Journal Title: {pub['journal_title']}")
    if pub['type'] == 'book':
        print(f"Book Title: {pub['book_title']}")
    if pub['type'] == 'book-chapter':
        print(f"Chapter Title: {pub['chapter_title']}")
        print(f"Book Title: {pub['book_title']}")
    print(f"Citation Count: {pub['citation_count'] if pub['citation_count'] is not None else 'Not available'}")
    print(f"Publication Date: {pub['publication_date'] if pub['publication_date'] else 'Not available'}")



#Final Iteration

from requests_html import HTMLSession
from bs4 import BeautifulSoup

def GetCredentialsFromORCID(orcid_id):
    
    import requests

    r = requests.get(f'https://pub.orcid.org/v3.0/expanded-search/?start=0&rows=200&q=orcid:{orcid_id}', headers={"accept": "application/json"})
    try:
        return r.json()
    except Exception as e:
        print(f"❌ ORCID request failed: {e}")
        

def GetPublicationsFromORCID(orcid_id, start_year, end_year):
    import requests
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {"accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"❌ ORCID API error: {r.status_code}")
        return []
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
                try:
                    pub_year_int = int(pub_year)
                    if not (start_year <= pub_year_int <= end_year):
                        continue
                except Exception:
                    continue
                # Build date string with available parts
                date_parts = [pub_year]
                if pub_month:
                    date_parts.append(pub_month)
                if pub_day:
                    date_parts.append(pub_day)
                pub_date = "-".join(date_parts)
                # Journal, Book, Chapter info
                journal_title = summary.get("journal-title", {}).get("value") if summary.get("journal-title") else None
                type_of_work = summary.get("type", "")
                book_title = None
                chapter_title = None
                publisher = summary.get("publisher", {}).get("value") if summary.get("publisher") else None
                # Authors
                authors = []
                contributors = summary.get("contributors", {}).get("contributor", []) if summary.get("contributors") else []
                for c in contributors:
                    # Try credit-name, then contributor-orcid if available
                    name = c.get("credit-name", {}).get("value")
                    if not name:
                        # Try to get name from contributor-orcid
                        orcid_obj = c.get("contributor-orcid", {}).get("path")
                        if orcid_obj:
                            name = orcid_obj
                    if name:
                        authors.append(name)
                # Fallback: use ORCID profile name if no contributors
                authors_str = ", ".join(authors) if authors else None
                if not authors_str:
                    # Try to get ORCID profile name from expanded search
                    try:
                        cred = GetCredentialsFromORCID(orcid_id)
                        if cred and 'expanded-result' in cred and len(cred['expanded-result']) > 0:
                            profile_name = cred['expanded-result'][0].get('given-names', '') + ' ' + cred['expanded-result'][0].get('family-name', '')
                            authors_str = profile_name.strip() if profile_name.strip() else None
                    except Exception:
                        pass
                # Citation count from Semantic Scholar
                citation_count = None
                if doi:
                    citation_count = GetCitationCountFromSemanticScholar(doi)
                if type_of_work == "journal-article":
                    # Collect all authors from all work summaries in the group
                    all_authors = []
                    for ws in work_summaries:
                        contributors = ws.get("contributors", {}).get("contributor", []) if ws.get("contributors") else []
                        for c in contributors:
                            name = c.get("credit-name", {}).get("value")
                            if not name:
                                orcid_obj = c.get("contributor-orcid", {}).get("path")
                                if orcid_obj:
                                    name = orcid_obj
                            if name:
                                all_authors.append(name)
                    # Remove duplicates and join
                    all_authors = list(dict.fromkeys(all_authors))
                    all_authors_str = ", ".join(all_authors) if all_authors else None
                    journal_rows.append({
                        "Authors": authors_str,
                        "All Authors": all_authors_str,
                        "Title": title,
                        "DOI": doi,
                        "Year": pub_year,
                        "Journal Title": journal_title,
                        "Citation Count": citation_count,
                        "Publication Date": pub_date
                    })
                elif type_of_work == "book":
                    book_rows.append({
                        "Authors": authors_str,
                        "Book Title": title,
                        "Year": pub_year,
                        "Publisher": publisher,
                        "Citation Count": citation_count,
                        "Publication Date": pub_date
                    })
                elif type_of_work == "book-chapter":
                    chapter_title = title
                    # Try to get book title from group
                    book_title = summary.get("container-title", {}).get("value") if summary.get("container-title") else None
                    chapter_rows.append({
                        "Authors": authors_str,
                        "Book Title": book_title,
                        "Chapter Title": chapter_title,
                        "Year": pub_year,
                        "Publisher": publisher,
                        "Citation Count": citation_count,
                        "Publication Date": pub_date
                    })
            else:
                print(f"⚠️ Skipping publication due to missing year or malformed data: {title}")
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
        # Print DataFrames
        if journal_rows:
            print("\nJournal Articles:")
            print(pd.DataFrame(journal_rows))
        if book_rows:
            print("\nBooks:")
            print(pd.DataFrame(book_rows))
        if chapter_rows:
            print("\nBook Chapters:")
            print(pd.DataFrame(chapter_rows))
        # Return all for further use if needed
        return {"journal": journal_rows, "book": book_rows, "chapter": chapter_rows}
    except Exception as e:
        print(f"Error in GetPublicationsFromORCID: {e}")
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
    return results

# Example usage
orcid_id = "0000-0002-6217-0430" 
start_year = 2019
end_year = 2024

publications = GetPublicationsFromORCID(orcid_id, start_year, end_year)
for cat, pubs in publications.items():
    print(f"\n--- {cat.capitalize()} ---")
    for pub in pubs:
        print("\n---")
        for k, v in pub.items():
            print(f"{k}: {v if v is not None else 'Not available'}")
