"""Check Jaeger traces."""
import requests
import json

r = requests.get('http://localhost:16686/api/traces?service=inference-api&limit=10')
data = r.json()
print(f'Total traces: {len(data.get("data", []))}')
for trace in data.get("data", []):
    spans = trace.get("spans", [])
    print(f"  Trace {trace.get('traceID','?')}: {len(spans)} spans")
    for s in spans[:5]:
        print(f"    span: {s.get('operationName')} ({s.get('duration')/1e6:.1f}ms)")
        attrs = {a['key']: a.get('value', '') for a in s.get('tags', []) if a['key'].startswith('gen_ai') or a['key'] in ('text.length', 'k')}
        if attrs:
            print(f"      attrs: {attrs}")