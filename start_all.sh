#!/usr/bin/env bash
set -e

# カレントディレクトリをスクリプト配置場所に固定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  🏥 CareLink 一括起動ランチャー (サーバー & トンネル)"
echo "=========================================================="

# 既存の uvicorn や cloudflared を停止
echo "1. 既存のバックエンド・トンネルプロセスを確認・停止中..."
pkill -f "uvicorn backend.main:app" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

# バックエンドサーバーの起動
echo "2. FastAPI バックエンドサーバーを起動中 (ポート 8000)..."
if [ ! -d ".venv" ]; then
    echo "❌ 仮想環境 .venv が見つかりません。セットアップを確認してください。"
    exit 1
fi

.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 > /tmp/carelink_backend.log 2>&1 &
SERVER_PID=$!

# サーバーの起動待ち
echo "3. バックエンドの応答を待機中..."
for i in {1..20}; do
    if curl -s http://localhost:8000/docs >/dev/null 2>&1; then
        echo "  ✅ バックエンドサーバーが正常に起動しました (PID: $SERVER_PID)"
        break
    fi
    sleep 1
done

# 終了時のクリーンアップ処理
cleanup() {
    echo ""
    echo "=========================================================="
    echo "  🛑 CareLink サービスを安全にシャットダウンしています..."
    echo "=========================================================="
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        echo "  ✅ バックエンドサーバーを停止しました。"
    fi
    pkill -f "cloudflared tunnel" 2>/dev/null || true
    echo "  ✅ すべてのプロセスを終了しました。"
    exit 0
}
trap cleanup INT TERM

# トンネルスクリプトを実行 (トンネル起動・GitHub同期・終了時ステータス更新を行う)
echo "4. Cloudflare トンネルを起動して GitHub Pages と同期します..."
./start_tunnel.sh

# トンネル終了後、サーバーも片付け
cleanup
