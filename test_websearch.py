import sys
sys.path.insert(0, r'D:\autoSage\backend')

from app.engine.tools.datasets import _search_web_datasets

# Test search for loan default dataset
results = _search_web_datasets('loan default dataset', limit=3)
print('Loan default search results:')
for r in results:
    url = r.get('url', '')[:60] if r.get('url') else 'N/A'
    print(f'  - {r["name"]} (url: {url})')

print()

# Test search for housing dataset
results = _search_web_datasets('housing regression dataset', limit=3)
print('Housing search results:')
for r in results:
    url = r.get('url', '')[:60] if r.get('url') else 'N/A'
    print(f'  - {r["name"]} (url: {url})')