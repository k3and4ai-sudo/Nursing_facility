#!/usr/bin/env bash
# Care-Link Tunnel Launcher (Cloudflare Quick Tunnel)
echo "=== Care-Link 外部接続トンネルを起動中... ==="
echo "手元PCのバックエンド (localhost:8000) を安全に外部公開します。"
echo "発行されたURL (https://xxxx.trycloudflare.com) をご家族ポータルに設定してください。"
echo "=================================================="
./cloudflared tunnel --url http://localhost:8000
