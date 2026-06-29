"""Check all rubric requirements."""
import requests
import json

# Check app
r = requests.get('http://localhost:8000/healthz', timeout=3)
print('app:', r.status_code)

# Check metrics
r = requests.get('http://localhost:8000/metrics', timeout=3)
metrics_text = r.text
checks = {
    'inference_requests_total': 'inference_requests_total' in metrics_text,
    'inference_latency_seconds_bucket': 'inference_latency_seconds_bucket' in metrics_text,
    'inference_active_gauge': 'inference_active_gauge' in metrics_text,
    'inference_quality_score': 'inference_quality_score' in metrics_text,
    'inference_tokens_total': 'inference_tokens_total' in metrics_text,
}
for k, v in checks.items():
    status = 'OK' if v else 'MISSING'
    print(f'  {k}: {status}')

# Check dashboards
r = requests.get('http://localhost:3000/api/search?query=Day%2023', auth=('admin','admin'), timeout=3)
dashboards = r.json()
dash_count = sum(1 for d in dashboards if d['type'] == 'dash-db')
print(f'dashboards: {dash_count} (need >= 3)')

# Check drift
with open('04-drift-detection/reports/drift-summary.json') as f:
    drift = json.load(f)
drifted = any(m.get('drift') == 'yes' for m in drift.values())
print(f'drift: {"OK" if drifted else "FAIL"}')

# Check reflection
with open('submission/REFLECTION.md') as f:
    refl = f.read()
print(f'reflection: {len(refl)} chars (need > 500)')

# Summary
all_ok = all(checks.values()) and dash_count >= 3 and drifted and len(refl) > 500
print(f'\nALL CHECKS: {"PASS" if all_ok else "FAIL"}')