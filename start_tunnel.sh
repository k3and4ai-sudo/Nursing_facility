#!/usr/bin/env bash
set -e

# カレントディレクトリをスクリプトの配置ディレクトリに固定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="/tmp/carelink_tunnel.log"
ENDPOINT_JSON="docs/tunnel_endpoint.json"
mkdir -p docs

echo "=========================================================="
echo "  🚀 Care-Link Cloudflare トンネル ＆ 自動同期ランチャー"
echo "=========================================================="
echo "1. 手元PCのバックエンド (localhost:8000) の外部公開を開始します..."

# 既存のcloudflaredプロセスを安全に終了
pkill -f "cloudflared tunnel" 2>/dev/null || true
rm -f "$LOG_FILE"

# バックグラウンドでcloudflaredを起動
./cloudflared tunnel --url http://localhost:8000 > "$LOG_FILE" 2>&1 &
TUNNEL_PID=$!

echo "2. トンネルURLの発行を待機中..."
TUNNEL_URL=""
for i in {1..35}; do
    sleep 1
    if [ -f "$LOG_FILE" ]; then
        FOUND_URL=$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' "$LOG_FILE" | head -n 1 || true)
        if [ -n "$FOUND_URL" ]; then
            TUNNEL_URL="$FOUND_URL"
            break
        fi
    fi
done

if [ -z "$TUNNEL_URL" ]; then
    echo "❌ トンネルURLの取得に失敗しました。ログを確認してください:"
    cat "$LOG_FILE"
    kill "$TUNNEL_PID" 2>/dev/null || true
    exit 1
fi

echo "=========================================================="
echo "  ✅ トンネルURLを発行しました: $TUNNEL_URL"
echo "=========================================================="

# JSONファイルを生成
UPDATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat <<EOF > "$ENDPOINT_JSON"
{
  "backend_url": "$TUNNEL_URL",
  "updated_at": "$UPDATED_AT"
}
EOF

# frontend/family にもコピー
cp "$ENDPOINT_JSON" frontend/family/tunnel_endpoint.json 2>/dev/null || true
cp frontend/family/app.js docs/app.js 2>/dev/null || true

echo "3. GitHub Pages へ最新トンネルURLを自動プッシュ中..."
git add "$ENDPOINT_JSON" frontend/family/tunnel_endpoint.json docs/app.js frontend/family/app.js
if git diff --staged --quiet; then
    echo "ℹ️ エンドポイントに変更はありません。"
else
    git commit -m "chore: auto-update tunnel endpoint [skip ci]"
    git push origin main
    echo "  🚀 GitHubへの反映が完了しました！"
fi

echo "=========================================================="
echo "  🎉 外部接続の準備が完了しました！"
echo "  📱 ご家族ポータル固定URL:"
echo "     https://k3and4ai-sudo.github.io/Nursing_facility/"
echo "     (※ スマホ側でURLの打ち直しは不要です。上記URLを開くだけで自動接続されます)"
echo "  🏠 居室端末 (外部・スマホ・タブレット用URL):"
echo "     $TUNNEL_URL/user/"
echo "=========================================================="
echo "トンネル稼働中... 停止するには Ctrl+C を押してください。"

# 終了ハンドラ
cleanup() {
    echo ""
    echo "トンネルを停止しています..."
    kill "$TUNNEL_PID" 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

wait "$TUNNEL_PID"
