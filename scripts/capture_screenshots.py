"""Capture screenshot evidence for rubric checkpoints via API."""
import requests
import json
from pathlib import Path
import time

SCREENSHOTS = Path(__file__).resolve().parent.parent / "submission" / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

GRAFANA_AUTH = ("admin", "admin")
GRAFANA_BASE = "http://localhost:3000"

def save_api_data(name: str, data):
    """Save API response data as evidence (dict, list, or str)."""
    path = SCREENSHOTS / f"{name}.json"
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data, indent=2))
    else:
        path.write_text(str(data))
    print(f"  saved: {path.name} ({len(path.read_text())} bytes)")

def save_html(name: str, content: str):
    """Save HTML content as evidence."""
    path = SCREENSHOTS / f"{name}.html"
    path.write_text(content)
    print(f"  saved: {path.name} ({len(content)} bytes)")

def get_dashboard_png(uid: str, name: str):
    """Try to get a dashboard PNG via Grafana rendering API."""
    url = f"{GRAFANA_BASE}/render/d-solo/{uid}?orgId=1&from=now-1h&to=now&width=1000&height=500"
    try:
        r = requests.get(url, auth=GRAFANA_AUTH, timeout=15)
        if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
            path = SCREENSHOTS / f"{name}.png"
            path.write_bytes(r.content)
            print(f"  saved: {path.name}")
        else:
            print(f"  ERROR: {url} returned {r.status_code}")
    except Exception as e:
        print(f"  ERROR: {e}")

def capture_grafana_panel(uid: str, panel_id: int, name: str):
    """Try rendering a specific panel via direct link."""
    url = f"{GRAFANA_BASE}/d-solo/{uid}/1?orgId=1&from=now-1h&to=now&panelId={panel_id}&width=1000&height=500"
    try:
        r = requests.get(url, auth=GRAFANA_AUTH, timeout=15)
        if r.status_code == 200:
            path = SCREENSHOTS / f"{name}.png"
            path.write_bytes(r.content)
            print(f"  saved: {path.name}")
        else:
            print(f"  Panel {panel_id}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  ERROR: {e}")

def capture_overview_dashboard():
    """Capture the AI Service Overview dashboard with data."""
    print("\n📊 AI Service Overview Dashboard:")
    uid = "day23-ai-overview"
    # Try rendering with Grafana image renderer
    get_dashboard_png(uid, "dashboard-overview")
    # Also save JSON model
    r = requests.get(f"{GRAFANA_BASE}/api/dashboards/uid/{uid}", auth=GRAFANA_AUTH, timeout=10)
    if r.status_code == 200:
        data = r.json()
        save_api_data("dashboard-overview-model", data)
        panels = data.get('dashboard', {}).get('panels', [])
        print(f"    Panels: {len(panels)}")
        for p in panels:
            print(f"      - {p.get('title', 'untitled')} (id={p.get('id','?')})")

def capture_slo_dashboard():
    """Capture SLO Burn Rate dashboard."""
    print("\n📈 SLO Burn Rate Dashboard:")
    uid = "day23-slo"
    get_dashboard_png(uid, "dashboard-slo-burn-rate")
    r = requests.get(f"{GRAFANA_BASE}/api/dashboards/uid/{uid}", auth=GRAFANA_AUTH, timeout=10)
    if r.status_code == 200:
        data = r.json()
        save_api_data("dashboard-slo-model", data)
        panels = data.get('dashboard', {}).get('panels', [])
        print(f"    Panels: {len(panels)}")

def capture_cost_tokens_dashboard():
    """Capture Cost & Tokens dashboard."""
    print("\n💰 Cost & Tokens Dashboard:")
    uid = "day23-cost-tokens"
    get_dashboard_png(uid, "dashboard-cost-tokens")
    r = requests.get(f"{GRAFANA_BASE}/api/dashboards/uid/{uid}", auth=GRAFANA_AUTH, timeout=10)
    if r.status_code == 200:
        data = r.json()
        save_api_data("dashboard-cost-model", data)
        panels = data.get('dashboard', {}).get('panels', [])
        print(f"    Panels: {len(panels)}")

def capture_alertmanager():
    """Capture Alertmanager state."""
    print("\n🔔 Alertmanager:")
    r = requests.get("http://localhost:9093/api/v2/alerts", timeout=10)
    if r.status_code == 200:
        save_api_data("alertmanager-alerts", r.json())
    # Also capture status
    r = requests.get("http://localhost:9093/-/healthy", timeout=5)
    if r.status_code == 200:
        save_api_data("alertmanager-healthy", "OK")

def capture_alert_proof():
    """Capture evidence of ServiceDown alert fire+resolve."""
    print("\n🚨 Alert Proof:")
    # Check Prometheus alerts
    r = requests.get("http://localhost:9090/api/v1/alerts", timeout=10)
    if r.status_code == 200:
        save_api_data("prometheus-alerts", r.json())
        alerts = r.json().get('data', {}).get('alerts', [])
        for a in alerts:
            print(f"    {a['labels'].get('alertname','?')}: {a.get('state','?')}")

def capture_jaeger():
    """Capture Jaeger traces."""
    print("\n🔍 Jaeger Traces:")
    # Get services
    r = requests.get("http://localhost:16686/api/services", timeout=10)
    if r.status_code == 200:
        save_api_data("jaeger-services", r.json())
    
    # Get traces for inference-api
    r = requests.get("http://localhost:16686/api/traces?service=inference-api&limit=5&lookback=1h", timeout=10)
    if r.status_code == 200:
        data = r.json()
        save_api_data("jaeger-traces", data)
        traces = data.get('data', [])
        print(f"    Traces: {len(traces)}")
        for t in traces[:3]:
            spans = t.get('spans', [])
            span_names = [s.get('operationName','?') for s in spans[:5]]
            print(f"      trace {t.get('traceID','')[:8]}: {len(spans)} spans: {', '.join(span_names)}")
            # Check GenAI semantic conventions
            genai_attrs = []
            for s in spans:
                for tag in s.get('tags', []):
                    if 'gen_ai' in tag.get('key', ''):
                        genai_attrs.append(tag)
            if genai_attrs:
                save_api_data(f"jaeger-trace-{t.get('traceID','')[:8]}-genai-attrs", genai_attrs)
                print(f"        GenAI attrs: {len(genai_attrs)}")

    # Get error trace (forced error)
    r = requests.get("http://localhost:16686/api/traces?service=inference-api&limit=10&tags=%7B%22error%22%3A%22true%22%7D&lookback=1h", timeout=10)
    if r.status_code == 200:
        data = r.json()
        traces = data.get('data', [])
        print(f"    Error traces: {len(traces)}")
        if traces:
            save_api_data("jaeger-error-traces", data)

def capture_drift():
    """Capture drift detection results."""
    print("\n📉 Drift Detection:")
    path = Path("04-drift-detection/reports/drift-summary.json")
    if path.exists():
        data = json.loads(path.read_text())
        save_api_data("drift-summary", data)
        for feature, metrics in data.items():
            print(f"    {feature}: PSI={metrics['psi']}, KL={metrics['kl']}, drift={metrics['drift']}")

def capture_metrics():
    """Capture /metrics output as evidence."""
    print("\n📏 Metrics:")
    r = requests.get("http://localhost:8000/metrics", timeout=10)
    if r.status_code == 200:
        # Only save the inference-related lines
        lines = [l for l in r.text.splitlines() if l.startswith('# HELP inference') or (not l.startswith('#') and 'inference' in l)]
        save_api_data("inference-metrics", '\n'.join(lines))
        print(f"    Inference metrics lines: {len(lines)}")

def capture_predict_response():
    """Capture a predict response with trace_id."""
    print("\n🎯 Predict Response:")
    r = requests.post("http://localhost:8000/predict", json={"prompt": "observability test"}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        save_api_data("predict-response", data)
        print(f"    trace_id: {data.get('trace_id','?')}, tokens: {data.get('input_tokens','?')}→{data.get('output_tokens','?')}")

def capture_logs():
    """Capture structured log lines."""
    print("\n📝 Structured Logs:")
    import subprocess
    result = subprocess.run(
        ["docker", "compose", "logs", "app", "--tail=10"],
        capture_output=True, text=True, timeout=10
    )
    if result.stdout:
        save_api_data("app-logs", result.stdout)
        # Find lines with trace_id
        for line in result.stdout.splitlines():
            if 'trace_id' in line:
                print(f"    Log line with trace_id: {line[:150]}...")

def capture_setup_report():
    """Capture setup report."""
    print("\n⚙️ Setup Report:")
    path = Path("00-setup/setup-report.json")
    if path.exists():
        data = json.loads(path.read_text())
        save_api_data("setup-report", data)
        print(f"    Docker: {data.get('docker', {}).get('version','?')}, RAM: {data.get('ram_gb_available','?')}GB")

def capture_integration():
    """Capture cross-day dashboard info."""
    print("\n🔗 Integration:")
    # Search for cross-day dashboard
    r = requests.get(f"{GRAFANA_BASE}/api/search?query=full-stack", auth=GRAFANA_AUTH, timeout=10)
    if r.status_code == 200:
        dashboards = r.json()
        if dashboards:
            save_api_data("integration-dashboards", dashboards)
            print(f"    Found: {len(dashboards)} dashboards")
        else:
            print("    No cross-day dashboard found in search")
    
    # Check Prometheus scrape config
    with open("02-prometheus-grafana/prometheus/prometheus.yml") as f:
        content = f.read()
        if 'day19' in content.lower() or 'day20' in content.lower():
            save_api_data("prometheus-scrape-config", content)
            print("    Prometheus has Day 19/20 scrape config stubs")

def main():
    print("=" * 60)
    print("📸 Day 23 Lab — Screenshot Evidence Capture")
    print("=" * 60)
    
    capture_setup_report()
    capture_metrics()
    capture_predict_response()
    capture_logs()
    capture_drift()
    capture_alertmanager()
    capture_alert_proof()
    capture_jaeger()
    capture_overview_dashboard()
    capture_slo_dashboard()
    capture_cost_tokens_dashboard()
    capture_integration()
    
    print("\n" + "=" * 60)
    print(f"✅ Screenshots saved to: {SCREENSHOTS}")
    files = list(SCREENSHOTS.glob("*"))
    for f in sorted(files):
        print(f"  {f.name}")
    print("=" * 60)
    print("Note: Grafana image rendering may not work without the renderer plugin.")
    print("For visual proofs, open these URLs in a browser and take screenshots:")
    print("  - Overview:   http://localhost:3000/d/day23-ai-overview/ai-service-overview-day-23")
    print("  - SLO:        http://localhost:3000/d/day23-slo/slo-burn-rate-day-23")
    print("  - Cost:       http://localhost:3000/d/day23-cost-tokens/cost-and-tokens-day-23")
    print("  - Jaeger:     http://localhost:16686/search?service=inference-api")
    print("  - Alerts:     http://localhost:9093/#/alerts")

if __name__ == "__main__":
    main()