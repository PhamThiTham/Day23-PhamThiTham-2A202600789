# Day 23 — Observability Stack Lab — Reflection

## 1. Setup & Instrumentation

The lab was run on Windows 10 with Docker Desktop (v29.5.3, Compose v5.1.4). The 7-service stack includes: FastAPI app (instrumented), Prometheus, Alertmanager, Grafana, Jaeger, Loki, and OTel Collector. All services are healthy and communicating:

- **FastAPI app** (`day23-app`): exposes `/metrics` with 6 metric families:
  - `inference_requests_total` (counter, labeled by model + status)
  - `inference_latency_seconds` (histogram with buckets [0.05–10.0]s)
  - `inference_active_gauge` (gauge — rises during load, returns to 0)
  - `inference_tokens_total` (counter, labeled by direction: input/output)
  - `inference_quality_score` (gauge, eval-as-metric [0–1])
  - `gpu_utilization_percent` (simulated)
- **Prometheus** scrapes the app every 15s and applies SLO burn-rate rules + AI quality rules.
- **Alertmanager** receives alerts and routes them to Slack (configured via webhook).
- **Grafana** has 3 auto-provisioned dashboards: Overview, SLO Burn Rate, Cost & Tokens.
- **Jaeger** receives OTLP traces via the OTel Collector with tail-sampling.
- **OTel Collector** uses composite tail-sampling: keep all errors + all slow (>2s) + 1% probabilistic.

## 2. Alerts & SLO Burn-Rate

Two alert rule groups are configured:

**ai-quality.yml:**
- `HighInferenceLatency` — fires when P99 latency > 2s for 5 minutes
- `ServiceDown` — fires when `up{job="inference-api"} == 0` for 1 minute
- `InferenceQualityDrop` — fires when avg quality score < 0.7 for 10 minutes

**slo-burn-rate.yml** (multi-window multi-burn-rate pattern):
- `SLOFastBurn` — 5m AND 1h windows > 14.4× normal rate (critical)
- `SLOSlowBurn` — 30m AND 6h windows > 6× normal rate (warning)

**Alert test**: Stopped the app container → `ServiceDown` fired after ~1 minute (confirmed via Alertmanager API `{"state":"active"}`). Restarted the app → alert resolved automatically (confirmed via `{"state":"resolved"}` appearing and eventually disappearing from active alerts).

## 3. Tracing & Tail-Sampling Math

The OTel Collector is configured with tail-sampling (`decision_wait: 30s`, `num_traces: 50000`):
- **keep-errors** policy: traces with status_code=ERROR are kept (guaranteed 100% retention for failed requests)
- **keep-slow** policy: traces with latency > 2000ms are kept
- **probabilistic-1pct** policy: 1% of remaining healthy traces are sampled

**Math**: If we receive 100 traces/second with 2% error rate:
- 2 error traces/sec → kept (by keep-errors)
- 98 healthy traces/sec → 1% = ~0.98 traces/sec kept (by probabilistic-1pct)
- Total: ~2.98 traces/sec stored out of 100 → ~97% reduction

This matches the observed behavior: most traces in Jaeger show individual spans rather than complete 4-span traces (predict → embed-text → vector-search → generate-tokens), because 99% of healthy traces are dropped by the probabilistic sampler.

An error trace was sent manually (`POST /predict {"fail": true}` → 503) which is retained in full by the keep-errors policy.

## 4. Structured Logs

The app emits structured JSON logs via structlog. Example log line with `trace_id`:

```json
{"model": "llama3-mock", "input_tokens": 4, "output_tokens": 54, "quality": 0.82, "duration_seconds": 0.1568, "trace_id": "6082f867a1c670d55594dd711f52b25e", "event": "prediction served", "level": "info", "timestamp": "2026-06-29T14:21:54.500673Z"}
```

## 5. Drift Detection (PSI / KL / KS)

Ran `drift_detect.py` on synthetic datasets (reference vs shifted):

| Feature | PSI | KL | KS Stat | Drift |
|---------|-----|----|---------|-------|
| prompt_length | 3.461 | 1.798 | 0.702 | yes |
| embedding_norm | 0.019 | 0.032 | 0.052 | no |
| response_length | 0.016 | 0.018 | 0.056 | no |
| response_quality | 8.849 | 13.501 | 0.941 | yes |

**Which test fits which feature type**:
- **PSI (Population Stability Index)**: Best for categorical/binned features and monitoring distribution shifts over time. Works by comparing the proportion of observations in each bin between reference and current. Threshold: >0.1 = moderate drift, >0.2 = significant drift. Good for monitoring production model inputs.
- **KL Divergence**: Measures information loss when using current distribution to approximate reference. Asymmetric — sensitive to differences in the reference distribution's tails. Best for continuous features where you care about rare events.
- **KS Test (Kolmogorov-Smirnov)**: Non-parametric test comparing empirical CDFs. Best for continuous features like `prompt_length`. Returns both a statistic and p-value. Sensitive to differences in distribution shape, location, and spread.
- **MMD (Maximum Mean Discrepancy)**: Best for high-dimensional data (embeddings, images) where other tests fail. Not implemented in this lab but would be ideal for detecting drift in embedding vectors.

**Recommendation**: For AI monitoring, use PSI as the primary guardrail (intuitive thresholds), KS for continuous numeric features, and MMD for embedding spaces.

## 6. Integration (Days 16–22)

The cross-day dashboard (`full-stack-dashboard.json`) was imported into Grafana. It contains 6 panels covering:
- Day 16: Cloud infra metrics (stub — "No Data" if services not running)
- Day 17: Pipeline metrics (stub)
- Day 18: Lakehouse metrics (stub)
- Day 19: Vector store metrics (Qdrant — configurable via `DAY19_QDRANT_URL`)
- Day 20: Model serving metrics (llama.cpp — configurable via `DAY20_LLAMACPP_METRICS_URL`)
- Day 22: Alignment metrics (stub)

The Prometheus scrape config includes commented-out job definitions for Days 19 and 20 that can be uncommented when those services are available.

## 7. The Single Change That Mattered Most

The single change that mattered most was instrumenting the FastAPI app with OpenTelemetry and Prometheus client libraries *before* building any dashboards or alerts. This decision — instrument-first, observe-second — ensured that when we later added Grafana panels, burn-rate alerts, and Jaeger tracing, the data was already flowing. Without metrics at the source, the entire observability stack would have been beautiful but empty infrastructure. The `inference_active_gauge` metric was particularly valuable: during the load test it rose to ~10 (matching the Locust concurrency setting) and returned to 0 when load stopped, proving that the end-to-end pipeline from app → Prometheus → Grafana was working correctly. This validated the entire observability chain in under 5 minutes and gave confidence that alerts and dashboards would have real data to display.