#!/usr/bin/env python3
from paper_count import GetPublicationsFromORCID

# Test with a known ORCID
orcid = "0000-0001-7787-314X"
print(f"Testing ORCID {orcid} from 2023 to 2025")
pubs = GetPublicationsFromORCID(orcid, 2023, 2025)

print(f"\nResults:")
print(f"Journals: {len(pubs.get('journal', []))} publications")
print(f"Books: {len(pubs.get('book', []))} publications")
print(f"Chapters: {len(pubs.get('chapter', []))} publications")

# Show some details
if pubs.get('journal'):
    print(f"\nFirst journal publication:")
    first = pubs['journal'][0]
    for k, v in list(first.items())[:5]:
        print(f"  {k}: {v}")
