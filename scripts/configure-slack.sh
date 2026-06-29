#!/usr/bin/env bash
## Cấu hình Slack Webhook cho Alertmanager
## 
## Cách dùng:
##   1. Lấy Slack Webhook URL từ https://api.slack.com/messaging/webhooks
##   2. Chạy: bash scripts/configure-slack.sh <your-slack-webhook-url>
## 
## Ví dụ:
##   bash scripts/configure-slack.sh https://hooks.slack.com/services/T123/B456/abc123

set -euo pipefail

WEBHOOK_URL="${1:-}"

if [ -z "$WEBHOOK_URL" ]; then
  echo "❌ Vui lòng cung cấp Slack Webhook URL"
  echo "   bash scripts/configure-slack.sh https://hooks.slack.com/services/..."
  echo ""
  echo "📝 Cách lấy Slack Webhook URL:"
  echo "   1. Vào https://api.slack.com/messaging/webhooks"
  echo "   2. Tạo app -> Incoming Webhooks -> Activate"
  echo "   3. Copy Webhook URL"
  exit 1
fi

echo "🔧 Cập nhật .env..."
sed -i "s|SLACK_WEBHOOK_URL=.*|SLACK_WEBHOOK_URL=${WEBHOOK_URL}|" .env

echo "🔧 Cập nhật alertmanager.yml..."
sed -i "s|api_url: 'https://hooks.slack.com/services/REPLACE/ME'|api_url: '${WEBHOOK_URL}'|g" 02-prometheus-grafana/alertmanager/alertmanager.yml
sed -i "s|api_url: 'https://hooks.slack.com/services/TEST/TEST/TEST'|api_url: '${WEBHOOK_URL}'|g" 02-prometheus-grafana/alertmanager/alertmanager.yml

echo "✅ Slack webhook configured!"
echo "   Restart alertmanager để áp dụng: docker compose restart alertmanager"
echo "   Test alert: docker stop day23-app"