"""Check Grafana dashboards."""
import requests

r = requests.get('http://localhost:3000/api/search?query=Day%2023', auth=('admin','admin'))
dashboards = r.json()
print(f'Found {len(dashboards)} dashboards/folders:')
for d in dashboards:
    print(f"  {d.get('title', '?'):40s} uid={d.get('uid','?')} type={d.get('type','?')}")