"""
backend/multimedia.py - Care-Link Multimedia & Digital Postcard Generation Engine.
Implements Option 1: High-definition seasonal artwork + AI-assisted conversation synthesis.
Clean provider architecture ready for future external image AI (Imagen 3 / DALL-E 3) if activated.
"""

import re
import datetime
from typing import List, Dict, Any, Optional

SEASONAL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "spring": {
        "key": "spring",
        "name": "春（桜と和みの庭）",
        "image_url": "/family/assets/sample_postcard_spring.jpg",
        "bgm_title": "春爛漫・琴と横笛の調べ BGM (15秒)",
        "greetings": "春の和みをお届けします。満開の桜の下で",
        "calligraphy": "春の和みを お届けします",
        "accent_color": "#e07a8b",
        "icon": "🌸",
        "scale_mood": "sakura"
    },
    "summer": {
        "key": "summer",
        "name": "夏（涼風の朝顔と風鈴）",
        "image_url": "/family/assets/sample_postcard_summer.jpg",
        "bgm_title": "清流と風鈴のアンビエント BGM (15秒)",
        "greetings": "夏の朝顔、涼しい風、心穏やかに。暑さ厳しき折、ご自愛ください",
        "calligraphy": "お元気ですか？ 夏の朝顔、涼しい風、心穏やかに",
        "accent_color": "#4a7c9d",
        "icon": "🌻",
        "scale_mood": "windchime"
    },
    "autumn": {
        "key": "autumn",
        "name": "秋（コスモスと縁側庭園）",
        "image_url": "/family/assets/sample_postcard.jpg",
        "bgm_title": "秋風のどかな和風アンビエント BGM (15秒)",
        "greetings": "おだやかな秋の日に… お元気で。秋の庭より",
        "calligraphy": "おだやかな 秋の日に… お元気で",
        "accent_color": "#c86d51",
        "icon": "🍁",
        "scale_mood": "autumn"
    },
    "winter": {
        "key": "winter",
        "name": "冬（紅椿と雪庭の灯り）",
        "image_url": "/family/assets/sample_postcard_winter.jpg",
        "bgm_title": "雪灯りと温もりのアコースティック BGM (15秒)",
        "greetings": "健やかに温かい冬をお過ごしください。庭の紅椿より",
        "calligraphy": "健やかに 温かい冬をお過ごしください",
        "accent_color": "#5a6e7f",
        "icon": "❄️",
        "scale_mood": "winter"
    }
}

def get_current_season() -> str:
    """Detects season from current calendar month."""
    month = datetime.datetime.now().month
    if month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    elif month in [9, 10, 11]:
        return "autumn"
    else:
        return "winter"

import os
import base64
import urllib.request
import json
import time
from backend import config, database as db

LAST_IMAGE_GEN_NOTICE: Optional[Dict[str, Any]] = None

def get_last_image_gen_notice() -> Optional[Dict[str, Any]]:
    global LAST_IMAGE_GEN_NOTICE
    return LAST_IMAGE_GEN_NOTICE

def generate_image_with_gemini(
    prompt: str,
    output_filename: str = "generated_gemini_etegami.jpg",
    model_name: str = "gemini-3-pro-image"
) -> Optional[str]:
    """
    Calls Google Gemini Image Generation model (default: gemini-3-pro-image, fallback: gemini-2.5-flash-image)
    via Google AI Studio REST API to dynamically generate and save an artwork.
    Returns relative URL (/family/assets/...) on success, or None on quota/error.
    """
    global LAST_IMAGE_GEN_NOTICE
    api_key = config.GEMINI_API_KEY
    if not api_key:
        print("[Gemini Image Gen Notice]: GEMINI_API_KEY is not configured.")
        LAST_IMAGE_GEN_NOTICE = {
            "has_error": True,
            "code": "CONFIG_MISSING",
            "model": model_name,
            "message": "Gemini APIキーが設定されていません。"
        }
        return None

    # Try requested model (gemini-3-pro-image), and fallback to flash if needed
    models_to_try = [model_name]
    if model_name != "gemini-2.5-flash-image":
        models_to_try.append("gemini-2.5-flash-image")

    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for p in parts:
                        if "inlineData" in p:
                            b64_data = p["inlineData"].get("data", "")
                            if b64_data:
                                img_bytes = base64.b64decode(b64_data)
                                assets_dir = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets")
                                docs_dir = os.path.join(os.path.dirname(config.BASE_DIR), "docs/assets")
                                os.makedirs(assets_dir, exist_ok=True)
                                os.makedirs(docs_dir, exist_ok=True)
                                
                                target_file = os.path.join(assets_dir, output_filename)
                                with open(target_file, "wb") as f_out:
                                    f_out.write(img_bytes)
                                docs_target = os.path.join(docs_dir, output_filename)
                                with open(docs_target, "wb") as f_out2:
                                    f_out2.write(img_bytes)
                                print(f"[Gemini Image Gen SUCCESS]: Saved {m} generated image to {output_filename}")
                                LAST_IMAGE_GEN_NOTICE = None
                                return f"/family/assets/{output_filename}"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[Gemini Image Gen Notice]: Model {m} returned HTTP {e.code} ({err_body[:100]}...). Falling back.")
            if e.code == 429:
                LAST_IMAGE_GEN_NOTICE = {
                    "has_error": True,
                    "code": 429,
                    "model": m,
                    "message": f"Google AI Studio 画像生成モデル ({m}) が利用枠制限 (HTTP 429: クォータ上限) に達しました。水彩画エンジンで絵手紙を生成しました。"
                }
            else:
                LAST_IMAGE_GEN_NOTICE = {
                    "has_error": True,
                    "code": e.code,
                    "model": m,
                    "message": f"Gemini 画像生成モデル ({m}) でエラーが発生しました (HTTP {e.code})。水彩画エンジンで生成しました。"
                }
        except Exception as e:
            print(f"[Gemini Image Gen Notice]: Model {m} call failed: {e}. Falling back.")
            LAST_IMAGE_GEN_NOTICE = {
                "has_error": True,
                "code": "NETWORK_OR_TIMEOUT",
                "model": m,
                "message": f"Gemini 画像生成モデルの通信に失敗しました ({e})。水彩画エンジンで生成しました。"
            }

    return None

def generate_image_with_pollinations(
    prompt: str,
    output_filename: str = "generated_pollinations_etegami.jpg"
) -> Optional[str]:
    """
    Calls Pollinations.ai free API (completely free, no API key or account required)
    to dynamically generate authentic artwork.
    Returns relative URL (/family/assets/...) on success, or None on failure.
    """
    global LAST_IMAGE_GEN_NOTICE
    import urllib.parse
    import requests
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        # Using model=turbo for fast, reliable, rate-limit-friendly free generation
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=600&model=turbo&nologo=true"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=25.0
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            img_bytes = resp.content
            assets_dir = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets")
            docs_dir = os.path.join(os.path.dirname(config.BASE_DIR), "docs/assets")
            os.makedirs(assets_dir, exist_ok=True)
            os.makedirs(docs_dir, exist_ok=True)

            target_file = os.path.join(assets_dir, output_filename)
            with open(target_file, "wb") as f_out:
                f_out.write(img_bytes)
            docs_target = os.path.join(docs_dir, output_filename)
            with open(docs_target, "wb") as f_out2:
                f_out2.write(img_bytes)
            print(f"[Pollinations Image Gen SUCCESS]: Saved free AI image to {output_filename} ({len(img_bytes)} bytes)")
            LAST_IMAGE_GEN_NOTICE = None
            return f"/family/assets/{output_filename}"
        else:
            print(f"[Pollinations Image Gen Notice]: Received HTTP {resp.status_code} ({len(resp.content)} bytes). Falling back to watercolor.")
    except Exception as e:
        print(f"[Pollinations Image Gen Notice]: Free generation failed: {e}. Falling back to watercolor.")
        LAST_IMAGE_GEN_NOTICE = {
            "has_error": True,
            "code": "POLLINATIONS_ERROR",
            "model": "pollinations.ai (無料)",
            "message": f"Pollinations無料画像AIの通信でエラーが発生しました ({e})。水彩画エンジンで生成しました。"
        }
    return None

def create_artistic_watercolor_image(
    motif: str,
    theme_title: str,
    season: str = "autumn",
    output_filename: str = "generated_watercolor_etegami.jpg"
) -> str:
    """
    Creates a dedicated high-quality Japanese watercolor / Etegami style artwork for novel resident motifs.
    Dynamically renders authentic washi texture, soft watercolor washes, ink line-work, and concrete motif
    artwork (e.g. cute puppy, cozy cat, gentle bird, seasonal flowers, tea cup, Mount Fuji, etc.).
    Saves to frontend/family/assets and docs/assets.
    """
    import random
    import math
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    w, h = 800, 600
    # Season palette definitions (soft washi tints & watercolor wash)
    palettes = {
        "spring": {
            "bg": (254, 250, 252),
            "wash1": (255, 222, 232, 90),
            "wash2": (255, 200, 215, 80),
            "accent": (216, 112, 147),
            "seal": "🌸",
            "flower_petal": (255, 185, 205, 210)
        },
        "summer": {
            "bg": (248, 252, 254),
            "wash1": (205, 238, 250, 90),
            "wash2": (180, 220, 235, 80),
            "accent": (70, 130, 180),
            "seal": "🌻",
            "flower_petal": (255, 210, 60, 220)
        },
        "autumn": {
            "bg": (253, 251, 245),
            "wash1": (252, 228, 200, 90),
            "wash2": (245, 210, 165, 85),
            "accent": (195, 95, 55),
            "seal": "🍁",
            "flower_petal": (230, 120, 140, 210)
        },
        "winter": {
            "bg": (250, 252, 255),
            "wash1": (225, 235, 246, 90),
            "wash2": (195, 210, 230, 80),
            "accent": (90, 115, 140),
            "seal": "❄️",
            "flower_petal": (205, 45, 55, 220)
        }
    }
    p = palettes.get(season, palettes["autumn"])

    # 1. Base Washi canvas
    img = Image.new("RGB", (w, h), p["bg"])
    draw = ImageDraw.Draw(img)

    # Subtle washi fiber grain
    for y in range(0, h, 6):
        for x in range(0, w, 6):
            n = random.randint(-4, 4)
            c = max(0, min(255, p["bg"][0] + n))
            draw.point((x, y), fill=(c, c - 2, max(0, c - 6)))

    # 2. Watercolor wash layers (soft blurred atmospheric aura)
    wash_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wash_layer)
    wdraw.ellipse([80, 60, 720, 540], fill=p["wash1"])
    wdraw.ellipse([160, 120, 640, 480], fill=p["wash2"])
    # Random gentle organic splashes
    for _ in range(6):
        rx = random.randint(140, 660)
        ry = random.randint(120, 480)
        rr = random.randint(60, 150)
        wdraw.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=(p["wash2"][0], p["wash2"][1], p["wash2"][2], 40))

    wash_layer = wash_layer.filter(ImageFilter.GaussianBlur(radius=28))
    img.paste(wash_layer, (0, 0), wash_layer)

    # 3. Dedicated Motif Painting Layer (Watercolor & Sumi-e)
    clean_motif = motif.replace("高校時代の", "").replace("昔の", "").replace("今日の", "").strip() or "心温まる思い出"
    m_lower = clean_motif.lower()

    # Create dedicated art layer
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(art)
    ink = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(ink)

    cx, cy = 400, 290  # center for illustration

    # Check motif category
    if any(k in clean_motif for k in ["犬", "子犬", "いぬ", "イヌ", "ワンちゃん", "ポチ", "柴犬", "わんこ", "puppy", "dog"]):
        # 🐶 Cute Etegami Watercolor Puppy
        has_zashiki = any(k in clean_motif for k in ["座敷", "和室", "畳", "縁側", "廊下", "部屋"])
        is_running = any(k in clean_motif for k in ["走", "駆", "かけっこ", "トコトコ", "ダッシュ", "回り", "回る", "回って"])
        is_front = any(k in clean_motif for k in ["こちら", "こっち", "手前", "前", "向かって"])
        is_white = ("白" in clean_motif or "しろ" in clean_motif)

        if has_zashiki:
            # 畳の敷かれた和室の床（穏やかな若草色・い草色の水彩ウォッシュ）
            adraw.rectangle([60, 220, 740, 520], fill=(215, 232, 195, 130))
            # 畳の縁（黒・濃紺のシックなライン）
            adraw.line([60, 340, 740, 340], fill=(55, 65, 55, 160), width=6)
            adraw.line([60, 460, 740, 460], fill=(55, 65, 55, 160), width=6)
            adraw.line([280, 220, 280, 340], fill=(55, 65, 55, 140), width=5)
            adraw.line([520, 340, 520, 460], fill=(55, 65, 55, 140), width=5)
            # 障子からの柔らかな日差し（光の帯）
            adraw.polygon([(90, 60), (270, 60), (460, 420), (210, 420)], fill=(255, 255, 230, 80))

        body_col = (255, 255, 252, 245) if is_white else (238, 198, 140, 235)
        ear_col = (242, 222, 202, 235) if is_white else (210, 160, 95, 245)

        if is_front and is_running:
            # 🐕 1. 正面からこちらへ元気に駆けてくる躍動ポーズ！
            # 畳の奥から手前へ続く足跡（遠近感のある肉球スタンプ）
            steps = [(cx - 20, cy - 40, 6), (cx + 25, cy + 10, 9), (cx - 35, cy + 60, 13), (cx + 30, cy + 110, 16)]
            for sx, sy, sr in steps:
                adraw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(195, 145, 135, 140))
                for ox, oy in [(-sr*0.6, -sr*0.9), (0, -sr*1.1), (sr*0.6, -sr*0.9)]:
                    adraw.ellipse([sx + ox - sr*0.25, sy + oy - sr*0.25, sx + ox + sr*0.25, sy + oy + sr*0.25], fill=(195, 145, 135, 140))

            # 疾走のスピード風ライン
            idraw.line([(cx - 160, cy + 50), (cx - 90, cy + 65)], fill=(120, 110, 100, 120), width=3)
            idraw.line([(cx - 180, cy + 80), (cx - 100, cy + 95)], fill=(120, 110, 100, 100), width=2)
            idraw.line([(cx + 90, cy + 65), (cx + 160, cy + 50)], fill=(120, 110, 100, 120), width=3)
            idraw.line([(cx + 100, cy + 95), (cx + 180, cy + 80)], fill=(120, 110, 100, 100), width=2)

            # 後ろ足（後ろに蹴り出し中）
            adraw.ellipse([cx - 110, cy + 70, cx - 60, cy + 115], fill=body_col)
            adraw.ellipse([cx + 60, cy + 70, cx + 110, cy + 115], fill=body_col)
            # 胴体（正面で少し弾んでいる）
            adraw.ellipse([cx - 85, cy - 10, cx + 85, cy + 130], fill=body_col)
            # しっぽ（嬉しそうに上へピコピコ）
            adraw.ellipse([cx + 60, cy - 35, cx + 110, cy + 25], fill=body_col)
            # 頭（手前で大きく愛らしく）
            adraw.ellipse([cx - 95, cy - 120, cx + 95, cy + 55], fill=body_col)
            # 耳（走る風で横後ろになびく）
            adraw.ellipse([cx - 135, cy - 90, cx - 65, cy - 20], fill=ear_col)
            adraw.ellipse([cx + 65, cy - 90, cx + 135, cy - 20], fill=ear_col)
            # 手前に大きく出された元気な前足
            adraw.ellipse([cx - 75, cy + 90, cx - 15, cy + 145], fill=body_col)
            adraw.ellipse([cx + 15, cy + 80, cx + 75, cy + 135], fill=body_col)

            art = art.filter(ImageFilter.GaussianBlur(radius=3))

            # 顔・表情（大喜びで走ってくるキラキラ笑顔）
            idraw.arc([cx - 65, cy + 25, cx + 65, cy + 55], start=10, end=170, fill=(215, 45, 45, 240), width=7)
            idraw.ellipse([cx - 9, cy + 48, cx + 9, cy + 66], fill=(240, 190, 45, 245))  # 鈴
            # 目
            idraw.ellipse([cx - 45, cy - 42, cx - 23, cy - 18], fill=(38, 28, 24, 245))
            idraw.ellipse([cx - 40, cy - 38, cx - 31, cy - 28], fill=(255, 255, 255, 255))
            idraw.ellipse([cx + 23, cy - 42, cx + 45, cy - 18], fill=(38, 28, 24, 245))
            idraw.ellipse([cx + 27, cy - 38, cx + 36, cy - 28], fill=(255, 255, 255, 255))
            # 鼻
            idraw.ellipse([cx - 15, cy - 15, cx + 15, cy + 6], fill=(42, 32, 28, 245))
            # 舌を出して楽しそうな口
            idraw.arc([cx - 18, cy + 2, cx, cy + 18], start=20, end=160, fill=(45, 35, 30, 210), width=3)
            idraw.arc([cx, cy + 2, cx + 18, cy + 18], start=20, end=160, fill=(45, 35, 30, 210), width=3)
            adraw.ellipse([cx - 8, cy + 12, cx + 8, cy + 28], fill=(245, 120, 130, 220))  # ピンクの舌

        elif is_running:
            # 🐕 2. 横向きで座敷を軽快に駆け回る疾走ポーズ！
            # 畳の上の疾走足跡
            for i, (px, py) in enumerate([(140, cy + 130), (220, cy + 115), (310, cy + 135), (420, cy + 120)]):
                adraw.ellipse([px - 10, py - 8, px + 10, py + 8], fill=(195, 145, 135, 130))
                adraw.ellipse([px - 8, py - 13, px - 3, py - 8], fill=(195, 145, 135, 130))
                adraw.ellipse([px - 1, py - 15, px + 4, py - 10], fill=(195, 145, 135, 130))
                adraw.ellipse([px + 5, py - 13, px + 10, py - 8], fill=(195, 145, 135, 130))

            # 駆け回る風ライン
            idraw.line([(cx - 240, cy + 20), (cx - 150, cy + 30)], fill=(120, 110, 100, 130), width=3)
            idraw.line([(cx - 260, cy + 50), (cx - 160, cy + 60)], fill=(120, 110, 100, 110), width=2)
            idraw.line([(cx - 230, cy + 80), (cx - 140, cy + 90)], fill=(120, 110, 100, 90), width=2)

            # 後ろ足を後ろへグッと蹴り上げ
            adraw.ellipse([cx - 160, cy + 40, cx - 80, cy + 85], fill=body_col)
            adraw.ellipse([cx - 180, cy + 70, cx - 110, cy + 105], fill=body_col)
            # 胴体（前傾姿勢で水平に伸びる）
            adraw.ellipse([cx - 110, cy - 10, cx + 80, cy + 95], fill=body_col)
            # しっぽ（後ろ斜め上にピンと立つ）
            adraw.ellipse([cx - 155, cy - 25, cx - 95, cy + 30], fill=body_col)
            # 頭（前方をしっかり見据える）
            adraw.ellipse([cx + 35, cy - 75, cx + 165, cy + 40], fill=body_col)
            # 耳（風になびいて後ろへ流れる）
            adraw.ellipse([cx - 25, cy - 65, cx + 45, cy - 10], fill=ear_col)
            adraw.ellipse([cx + 30, cy - 75, cx + 90, cy - 20], fill=ear_col)
            # 前足を前方へ力強く伸ばす
            adraw.ellipse([cx + 60, cy + 60, cx + 145, cy + 105], fill=body_col)
            adraw.ellipse([cx + 120, cy + 85, cx + 175, cy + 120], fill=body_col)

            art = art.filter(ImageFilter.GaussianBlur(radius=3))

            # 首輪
            idraw.line([(cx + 45, cy + 5), (cx + 55, cy + 45)], fill=(215, 45, 45, 240), width=7)
            idraw.ellipse([cx + 50, cy + 42, cx + 66, cy + 58], fill=(240, 190, 45, 245))
            # 目（いきいきと前を向く）
            idraw.ellipse([cx + 100, cy - 35, cx + 122, cy - 15], fill=(38, 28, 24, 245))
            idraw.ellipse([cx + 106, cy - 31, cx + 114, cy - 23], fill=(255, 255, 255, 255))
            # 鼻・口
            idraw.ellipse([cx + 145, cy - 15, cx + 168, cy + 4], fill=(42, 32, 28, 245))
            idraw.arc([cx + 130, cy - 5, cx + 155, cy + 18], start=20, end=160, fill=(45, 35, 30, 210), width=3)

        else:
            # 🐕 3. お座りポーズ（穏やかにくつろぐ子犬）
            # 足元の影
            adraw.ellipse([cx - 130, cy + 130, cx + 130, cy + 175], fill=(210, 200, 190, 80))
            # 胴体
            adraw.ellipse([cx - 105, cy - 25, cx + 105, cy + 150], fill=body_col)
            # しっぽ
            adraw.ellipse([cx + 75, cy + 30, cx + 135, cy + 90], fill=body_col)
            # 頭
            adraw.ellipse([cx - 90, cy - 135, cx + 90, cy + 45], fill=body_col)
            # 耳
            adraw.ellipse([cx - 115, cy - 110, cx - 55, cy - 15], fill=ear_col)
            adraw.ellipse([cx + 55, cy - 110, cx + 115, cy - 15], fill=ear_col)
            # 前足
            adraw.ellipse([cx - 70, cy + 120, cx - 18, cy + 160], fill=body_col)
            adraw.ellipse([cx + 18, cy + 120, cx + 70, cy + 160], fill=body_col)

            art = art.filter(ImageFilter.GaussianBlur(radius=3))

            # 首輪
            idraw.arc([cx - 68, cy + 15, cx + 68, cy + 48], start=10, end=170, fill=(215, 45, 45, 240), width=7)
            idraw.ellipse([cx - 9, cy + 40, cx + 9, cy + 58], fill=(240, 190, 45, 245))
            # 目
            idraw.ellipse([cx - 44, cy - 52, cx - 24, cy - 30], fill=(38, 28, 24, 245))
            idraw.ellipse([cx - 40, cy - 49, cx - 33, cy - 42], fill=(255, 255, 255, 255))
            idraw.ellipse([cx + 24, cy - 52, cx + 44, cy - 30], fill=(38, 28, 24, 245))
            idraw.ellipse([cx + 27, cy - 49, cx + 34, cy - 42], fill=(255, 255, 255, 255))
            # 鼻・口
            idraw.ellipse([cx - 15, cy - 25, cx + 15, cy - 4], fill=(42, 32, 28, 245))
            idraw.arc([cx - 18, cy - 10, cx, cy + 9], start=20, end=160, fill=(45, 35, 30, 210), width=3)
            idraw.arc([cx, cy - 10, cx + 18, cy + 9], start=20, end=160, fill=(45, 35, 30, 210), width=3)
            # 足跡
            idraw.ellipse([cx - 240, cy + 120, cx - 215, cy + 140], fill=(215, 140, 130, 140))
            idraw.ellipse([cx - 245, cy + 105, cx - 235, cy + 117], fill=(215, 140, 130, 140))
            idraw.ellipse([cx - 230, cy + 100, cx - 220, cy + 112], fill=(215, 140, 130, 140))
            idraw.ellipse([cx - 215, cy + 105, cx - 205, cy + 117], fill=(215, 140, 130, 140))

    elif any(k in clean_motif for k in ["猫", "ねこ", "ネコ", "子猫", "三毛猫", "cat"]):
        # 🐱 Cozy Etegami Cat
        adraw.ellipse([cx - 110, cy + 130, cx + 110, cy + 170], fill=(210, 200, 190, 80))
        adraw.ellipse([cx - 95, cy - 15, cx + 95, cy + 145], fill=(255, 252, 245, 235))  # Body
        adraw.ellipse([cx + 65, cy + 50, cx + 130, cy + 95], fill=(230, 160, 100, 230))  # Calico patch
        adraw.ellipse([cx - 85, cy - 120, cx + 85, cy + 30], fill=(255, 252, 245, 245))  # Head
        # Ears (pointed)
        adraw.polygon([(cx - 75, cy - 85), (cx - 50, cy - 145), (cx - 15, cy - 95)], fill=(250, 215, 205, 235))
        adraw.polygon([(cx + 15, cy - 95), (cx + 50, cy - 145), (cx + 75, cy - 85)], fill=(250, 215, 205, 235))
        art = art.filter(ImageFilter.GaussianBlur(radius=3))

        # Happy eyes, nose, whiskers
        idraw.arc([cx - 45, cy - 50, cx - 18, cy - 28], start=200, end=340, fill=(45, 35, 30, 230), width=3)
        idraw.arc([cx + 18, cy - 50, cx + 45, cy - 28], start=200, end=340, fill=(45, 35, 30, 230), width=3)
        idraw.ellipse([cx - 8, cy - 30, cx + 8, cy - 16], fill=(235, 120, 130, 240))
        # Whiskers
        idraw.line([(cx - 50, cy - 25), (cx - 105, cy - 35)], fill=(65, 55, 50, 160), width=2)
        idraw.line([(cx - 50, cy - 20), (cx - 105, cy - 15)], fill=(65, 55, 50, 160), width=2)
        idraw.line([(cx + 50, cy - 25), (cx + 105, cy - 35)], fill=(65, 55, 50, 160), width=2)
        idraw.line([(cx + 50, cy - 20), (cx + 105, cy - 15)], fill=(65, 55, 50, 160), width=2)

    elif any(k in clean_motif for k in ["鳥", "小鳥", "雀", "すずめ", "ことり", "bird"]):
        # 🕊️ Pair of Gentle Sparrows
        adraw.ellipse([cx - 60, cy - 50, cx + 60, cy + 60], fill=(225, 175, 125, 230))  # Sparrow body
        adraw.ellipse([cx - 45, cy - 110, cx + 45, cy - 25], fill=(195, 135, 85, 240))  # Head
        adraw.ellipse([cx - 30, cy - 20, cx + 30, cy + 50], fill=(255, 250, 242, 230))  # White breast
        # Branch
        idraw.line([(cx - 160, cy + 90), (cx + 160, cy + 50)], fill=(95, 75, 60, 220), width=7)
        # Beak & Eye
        idraw.polygon([(cx + 40, cy - 70), (cx + 62, cy - 62), (cx + 40, cy - 55)], fill=(220, 160, 45, 240))
        idraw.ellipse([cx + 15, cy - 75, cx + 27, cy - 63], fill=(35, 25, 20, 240))
        idraw.ellipse([cx + 18, cy - 73, cx + 22, cy - 69], fill=(255, 255, 255, 255))
        art = art.filter(ImageFilter.GaussianBlur(radius=3))

    elif any(k in clean_motif for k in ["富士", "富士山", "山", "夕日", "夕焼け", "夕暮れ", "mountain"]):
        # 🗻 Serene Mount Fuji & Sunset
        # Sun / Sky wash
        adraw.ellipse([cx - 120, cy - 170, cx + 120, cy + 70], fill=(255, 130, 95, 170))
        # Mountain base
        adraw.polygon([(cx - 240, cy + 140), (cx, cy - 80), (cx + 240, cy + 140)], fill=(75, 115, 165, 220))
        # Snow cap
        adraw.polygon([(cx - 70, cy - 15), (cx, cy - 80), (cx + 70, cy - 15)], fill=(255, 255, 255, 240))
        art = art.filter(ImageFilter.GaussianBlur(radius=4))

    elif any(k in clean_motif for k in ["茶", "湯呑み", "カフェ", "コーヒー", "珈琲", "tea", "coffee"]):
        # 🍵 Warm Tea Cup with Steam
        adraw.ellipse([cx - 100, cy + 110, cx + 100, cy + 150], fill=(130, 85, 55, 220))  # Saucer
        adraw.rectangle([cx - 70, cy - 30, cx + 70, cy + 100], fill=(245, 242, 235, 240))  # Cup body
        adraw.ellipse([cx - 70, cy + 70, cx + 70, cy + 115], fill=(245, 242, 235, 240))
        adraw.ellipse([cx - 70, cy - 50, cx + 70, cy - 10], fill=(125, 175, 95, 230))   # Green tea surface
        art = art.filter(ImageFilter.GaussianBlur(radius=3))
        # Steam lines
        idraw.arc([cx - 35, cy - 120, cx - 5, cy - 55], start=120, end=300, fill=(180, 170, 160, 160), width=3)
        idraw.arc([cx + 5, cy - 140, cx + 35, cy - 75], start=120, end=300, fill=(180, 170, 160, 160), width=3)

    else:
        # 🌸 Seasonal Etegami Flower & Motif Art (Universal)
        # Blooming watercolor flower petals
        petal_color = p.get("flower_petal", (245, 140, 160, 210))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            px = cx + int(math.cos(rad) * 65)
            py = cy + int(math.sin(rad) * 65)
            adraw.ellipse([px - 45, py - 45, px + 45, py + 45], fill=petal_color)
        adraw.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill=(255, 225, 75, 240))  # Flower center
        # Leaves
        adraw.ellipse([cx - 150, cy + 60, cx - 60, cy + 120], fill=(115, 175, 95, 200))
        adraw.ellipse([cx + 60, cy + 60, cx + 150, cy + 120], fill=(115, 175, 95, 200))
        art = art.filter(ImageFilter.GaussianBlur(radius=3))
        idraw.arc([cx - 35, cy - 35, cx + 35, cy + 35], start=0, end=360, fill=(160, 95, 35, 180), width=2)

    # Composite watercolor art and ink layers onto washi canvas
    img.paste(art, (0, 0), art)
    img.paste(ink, (0, 0), ink)

    # Re-obtain draw after composite
    draw = ImageDraw.Draw(img)

    # 4. Soft decorative watercolor frame (hand-brushed inner boundary)
    inset = 35
    for i in range(3):
        color_val = (p["accent"][0], p["accent"][1], p["accent"][2])
        draw.rectangle([inset + i, inset + i, w - inset - i, h - inset - i], outline=color_val, width=1)

    # 4-2. Poetic Calligraphic Caption (絵手紙の毛筆添え書き)
    font_path = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

    caption_text = ""
    if any(k in clean_motif for k in ["こちら", "こっち", "手前", "前"]):
        caption_text = "こちらへおいで\n元気な足音"
    elif any(k in clean_motif for k in ["走", "駆", "かけっこ", "トコトコ", "回り", "回る"]):
        caption_text = "元気に駆ける\n座敷のぬくもり" if any(k in clean_motif for k in ["座敷", "和室", "畳"]) else "トコトコ元気に\n走る足音"
    elif any(k in clean_motif for k in ["座敷", "和室", "畳"]):
        caption_text = "畳のぬくもり\nほっと一息"
    elif any(k in clean_motif for k in ["犬", "子犬", "わんこ", "柴犬"]):
        caption_text = "いつもそばに\nあたたかな温もり"
    elif any(k in clean_motif for k in ["猫", "ねこ"]):
        caption_text = "日だまりの中で\nのんびりと"
    elif any(k in clean_motif for k in ["鳥", "小鳥", "雀"]):
        caption_text = "寄り添う心\n優しい歌声"
    elif any(k in clean_motif for k in ["富士", "山"]):
        caption_text = "夕日に映える\n雄大な峰"
    elif any(k in clean_motif for k in ["茶", "カフェ", "コーヒー"]):
        caption_text = "心やすらぐ\n一服の温もり"
    else:
        caption_text = "季節の彩り\n心からありがとう"

    if caption_text:
        try:
            caption_font = ImageFont.truetype(font_path, 28) if os.path.exists(font_path) else ImageFont.load_default()
            lines = caption_text.split("\n")
            cur_y = 65
            for line in lines:
                draw.text((67, cur_y + 1), line, fill=(180, 170, 160, 120), font=caption_font)
                draw.text((66, cur_y), line, fill=(45, 40, 36, 235), font=caption_font)
                cur_y += 38
        except Exception as e_txt:
            print(f"[Artistic Caption Notice]: {e_txt}")

    # 5. Hanko stamp mark (bottom right, traditional Japanese red seal)
    font_path = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

    try:
        sub_font = ImageFont.truetype(font_path, 22) if os.path.exists(font_path) else ImageFont.load_default()
        stamp_x = w - inset - 75
        stamp_y = h - inset - 75
        draw.rectangle([stamp_x, stamp_y, stamp_x + 48, stamp_y + 48], outline=(185, 48, 38), width=2)
        seal_char = "和" if season != "spring" else "絆"
        draw.text((stamp_x + 12, stamp_y + 11), seal_char, fill=(185, 48, 38), font=sub_font)
    except Exception as e_seal:
        print(f"[Artistic Seal Draw Notice]: {e_seal}")

    # 6. Save output
    assets_dir = os.path.join(os.path.dirname(config.BASE_DIR), "frontend/family/assets")
    docs_dir = os.path.join(os.path.dirname(config.BASE_DIR), "docs/assets")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)

    target_file = os.path.join(assets_dir, output_filename)
    img.save(target_file, quality=95)
    docs_target = os.path.join(docs_dir, output_filename)
    try:
        img.save(docs_target, quality=95)
    except Exception:
        pass

    print(f"[Artistic Watercolor SUCCESS]: Generated dedicated artwork for '{clean_motif}' -> {output_filename}")
    return f"/family/assets/{output_filename}"

LAST_USED_IMAGE_ENGINE: Dict[str, Any] = {
    "engine": "local_watercolor",
    "name": "自立水彩画 (Local)",
    "type": "local",
    "desc": "ローカル水彩画エンジン（自前描画）"
}

def get_last_used_image_engine() -> Dict[str, Any]:
    global LAST_USED_IMAGE_ENGINE
    return dict(LAST_USED_IMAGE_ENGINE)

def translate_motif_for_etegami_art(motif: str) -> str:
    """Translates resident motif keywords to expressive English descriptions for watercolor painting."""
    m = motif.lower()
    translations = [
        ("白", "white"), ("黒", "black"), ("柴犬", "shiba inu puppy dog"),
        ("犬", "cute friendly puppy dog"), ("わんこ", "cute puppy"),
        ("猫", "gentle cozy Japanese cat"), ("ねこ", "gentle cozy cat"),
        ("インコ", "cute colorful parakeet bird"), ("小鳥", "gentle Japanese sparrow bird"),
        ("鳥", "peaceful singing bird"), ("すずめ", "little sparrow bird"),
        ("桜", "spring cherry blossoms"), ("さくら", "blooming cherry blossoms"),
        ("コスモス", "blooming pink cosmos flowers in autumn garden"), ("秋桜", "pink cosmos flowers"),
        ("紅葉", "vibrant red autumn maple leaves"), ("もみじ", "red maple leaves"),
        ("向日葵", "bright blooming sunflower"), ("ひまわり", "sunflower"),
        ("朝顔", "fresh morning glory flowers with dew drops"),
        ("富士山", "majestic Mount Fuji with soft morning clouds"),
        ("お茶", "traditional Japanese green tea cup with gentle steam"),
        ("縁側", "traditional Japanese engawa wooden porch with garden view"),
        ("喫茶店", "cozy retro Japanese kissaten coffee shop with coffee cup"),
        ("椿", "red camellia flower on fresh winter snow"),
        ("雪", "quiet peaceful winter snow garden")
    ]
    english_elements = []
    for k, v in translations:
        if k in motif:
            english_elements.append(v)
    if english_elements:
        return " and ".join(english_elements)
    return motif

def generate_new_etegami_artwork(
    motif: str,
    theme_title: str,
    season: str = "autumn",
    user_id: int = 1,
    engine: str = "pollinations"
) -> str:
    """
    Generates a completely new digital postcard artwork for novel resident memories or topics.
    Supports engine="pollinations" (free, no key) and engine="google_image" (paid).
    If chosen provider is unavailable or quota-limited (429), gracefully falls back to procedural watercolor.
    Always returns a functional relative image URL.
    """
    global LAST_USED_IMAGE_ENGINE
    clean_motif = motif.replace("高校時代の", "").replace("昔の", "").replace("今日の", "").strip() or "心温まる情景"
    timestamp = int(time.time())
    output_filename = f"generated_custom_etegami_{user_id}_{timestamp}.jpg"

    english_motif = translate_motif_for_etegami_art(clean_motif)

    # Construct rich English prompt for Japanese watercolor / Etegami style
    prompt = (
        f"A beautiful and peaceful Japanese watercolor painting, traditional Etegami art style. "
        f"Depicting {english_motif}, gentle natural light, nostalgic serene atmosphere, "
        f"soft pastel watercolor wash on textured washi paper, calming Japanese aesthetic, high resolution masterpiece."
    )

    is_paid_requested = engine in ["google_image", "paid", "google", "有料"]

    if is_paid_requested:
        print(f"[Etegami Generation]: Resident selected Google Image (Paid) for motif '{clean_motif}'")
        # 1. Try Gemini Image Generation (Paid)
        generated_url = generate_image_with_gemini(
            prompt=prompt,
            output_filename=output_filename,
            model_name="gemini-3.1-flash-image"
        )
        if generated_url:
            LAST_USED_IMAGE_ENGINE = {
                "engine": "gemini_imagen",
                "name": "Google Image (有料)",
                "type": "cloud_paid",
                "desc": "Google AI Studio クラウド画像生成 (有料版)"
            }
            return generated_url

        print("[Etegami Generation]: Google Image quota/error. Trying Pollinations.ai fallback before watercolor.")
        # Fallback to Pollinations if Google Image fails
        poll_url = generate_image_with_pollinations(
            prompt=prompt,
            output_filename=output_filename
        )
        if poll_url:
            LAST_USED_IMAGE_ENGINE = {
                "engine": "pollinations_fallback",
                "name": "Pollinations.ai (無料自動切替)",
                "type": "cloud_free",
                "desc": "有料版クォータ超過に伴い無料AI (Pollinations) で生成"
            }
            return poll_url
    else:
        print(f"[Etegami Generation]: Resident selected Pollinations.ai (Free) for motif '{clean_motif}'")
        # 1. Try Pollinations.ai (Completely Free)
        generated_url = generate_image_with_pollinations(
            prompt=prompt,
            output_filename=output_filename
        )
        if generated_url:
            LAST_USED_IMAGE_ENGINE = {
                "engine": "pollinations",
                "name": "Pollinations.ai (無料)",
                "type": "cloud_free",
                "desc": "Pollinations.ai 完全無料AI画像生成"
            }
            return generated_url

    # 2. Resilient Fallback: Create dedicated procedural Japanese watercolor image
    LAST_USED_IMAGE_ENGINE = {
        "engine": "local_watercolor",
        "name": "自立水彩画 (Local)",
        "type": "local",
        "desc": "ローカル水彩画エンジン（通信障害・制限時も自立稼働）"
    }
    return create_artistic_watercolor_image(
        motif=clean_motif,
        theme_title=theme_title,
        season=season,
        output_filename=output_filename
    )

def get_all_templates() -> List[Dict[str, Any]]:
    """Returns the list of all seasonal templates for UI selection."""
    return list(SEASONAL_TEMPLATES.values())

def extract_image_prompt_from_conversation(
    user_id: int,
    terminal_id: str,
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Analyzes conversation history using local Ollama LLM (or fallback heuristic)
    and extracts structured JSON payload for image generation and digital postcard synthesis.
    Saves the extracted JSON into the database for persistent access by family mode and staff.
    """
    if not chat_history:
        chat_history = db.get_chat_history(user_id, limit=40)

    # Slice only the latest conversational session (gap > 5 minutes or explicit session finish)
    if chat_history:
        session_turns = []
        for i in range(len(chat_history) - 1, -1, -1):
            curr_turn = chat_history[i]
            session_turns.insert(0, curr_turn)
            if i > 0:
                prev_turn = chat_history[i - 1]
                t_curr = curr_turn.get("timestamp", "")
                t_prev = prev_turn.get("timestamp", "")
                prev_msg = prev_turn.get("message", "")
                if any(term in prev_msg for term in ["終わります", "終了します", "失礼します", "ここら辺にします"]):
                    break
                try:
                    dt_curr = datetime.datetime.fromisoformat(t_curr)
                    dt_prev = datetime.datetime.fromisoformat(t_prev)
                    # If idle gap between turns is over 5 minutes, consider it a new session
                    if (dt_curr - dt_prev).total_seconds() > 300:
                        break
                except Exception:
                    pass
        chat_history = session_turns

    # Filter meaningful user messages (exclude operational and short greetings)
    user_turns = []
    for h in chat_history:
        if h.get("sender") == "user":
            msg = h.get("message", "").strip()
            # Exclude short test/operational remarks
            if len(msg) >= 2 and not any(k in msg for k in ["テスト", "聞こえますか", "聞こえてますか"]):
                user_turns.append(msg)

    if not user_turns:
        # Fallback to general recent messages if all were filtered
        user_turns = [h.get("message", "").strip() for h in chat_history if h.get("sender") == "user"][-5:]

    conversation_text = "\n".join([f"- {t}" for t in user_turns])
    detected_season = get_current_season()

    system_prompt = """あなたは高齢者ケア施設「Care-Link」の思い出・デジタル絵手紙AIプロデューサーです。
利用者の会話内容を分析し、ご家族向けデジタルポストカードおよび画像生成AI用の構造化JSONを抽出・生成してください。

会話は主に「① 昔の思い出・回想法」「② 相談事・お悩み・愚痴」「③ 日常生活・これからの楽しみ」のいずれかです。

【重要：個人情報・プライバシー・安心感への配慮原則】
1. 具体的な金額（「○万円」「○円」等）や個人の実名・銀行名などは【絶対にJSONやプロンプトに出力しない】でください。抽象化してください。
2. 相談事・お悩み・愚痴の場合、不安や孤独・病気・お金を直接描く暗い絵にしてはいけません。【心の荷物を下ろす安らぎのヒーリングアート（温かい緑茶、寄り添う二羽の小鳥、実りの稲穂、微笑むお地蔵様、木漏れ日の縁側など）】に昇華してください。
3. ご家族への要約文（summary_for_family）では、相談内容を直接暴露せず、「今日はお茶を飲みながら色々なお気持ちをゆっくりお話しされ、安心されたご様子でした」のようにプライバシーに配慮した温かい見守り報告にしてください。
4. 全ての項目は会話から無理に引き出す必要はありません。会話にない項目は一般的な安らぎの要素で自然に補ってください。

【必須出力フォーマット（JSONのみを出力してください）】
■ パターンA：相談事・お悩み・愚痴の場合（topic_category = "consultation"）
{
  "topic_category": "consultation",
  "consultation_type": "money_or_procedure" または "interpersonal" または "daily_complaint" または "general_anxiety" または "other",
  "privacy_safe_topic": "抽象化したテーマ（20文字以内。例: 友達とのお付き合い、家族への想い、日々のつぶやき）",
  "season": "spring" または "summer" または "autumn" または "winter",
  "consultation_details": {
    "relationship_target": "誰との関係か（例: 施設のお仲間、ご家族、昔の知人、自分自身等。言及がない場合はnull）",
    "trigger_or_context": "きっかけや具体的な出来事（例: 話しかけるタイミング、最近の寂しさ等。言及がない場合はnull）",
    "personal_tendency": "本人の性格や想い（例: 少し人見知り、ゆっくり付き合いたい等。言及がない場合はnull）"
  },
  "emotional_transition": {
    "user_feeling": "受容した利用者の気持ち（例: 不安、寂しさ、戸惑い等）",
    "comforting_goal": "届ける安らぎ（例: 安堵、温もり、肩の荷が下りる感覚等）"
  },
  "image_generation_prompt": {
    "positive_prompt": "Detailed English prompt for healing Japanese watercolor or Etegami art. Depicting a comforting, serene scene that brings relief and peace (e.g. gentle warm sunlight on a wooden porch with a cup of green tea, two cute sparrows snuggling together, golden ripe rice ears under calm sunset, gentle smiling Jizo statue, blooming wildflowers). Pastel colors, soothing atmosphere, masterpiece.",
    "negative_prompt": "dark, scary, depressing, crying, illness, money, currency, bank notes, hospital, modern gadgets, realistic, text, watermark",
    "art_style": "Japanese Watercolor / Healing Etegami (癒しの絵手紙・水彩画風)",
    "aspect_ratio": "4:3",
    "healing_motif": "teacup_and_sunlight" または "sparrows_together" または "golden_harvest" または "gentle_jizo" または "seasonal_flowers"
  },
  "postcard_metadata": {
    "headline": "ポストカードの題名（例: ほっと一息、実りの秋、あたたかな陽だまり等。20文字以内）",
    "calligraphy_message": "絵手紙風の優しい短文（例: 話してくれてありがとう、肩の力を抜いてのんびり、いつも心はそばにある等。20文字以内）",
    "summary_for_family": "ご家族向けプライバシー配慮型見守り報告（80文字程度）",
    "recommended_bgm_mood": "flowing_water" または "peaceful_ambient" または "warm_acoustic",
    "stamp_icon": "🍵" または "🌾" または "🕊️" または "☀️" または "🌸"
  }
}

■ パターンB：昔の思い出・回想法・日常の場合（topic_category = "childhood_memory" または "daily_life"）
{
  "topic_category": "childhood_memory" または "daily_life" または "future_wish",
  "season": "spring" または "summer" または "autumn" または "winter",
  "theme": "会話のテーマ（20文字以内）",
  "reminiscence_elements": {
    "era": "思い出の時代（例: 昭和レトロ、小学校時代等）",
    "location": "場所（例: 小学校の校庭、縁側等）",
    "people_involved": ["登場人物のリスト"],
    "food_or_objects": ["食べ物や小道具のリスト"],
    "emotional_tone": "感情・雰囲気（例: 懐かしさ、家族の団らん等）"
  },
  "image_generation_prompt": {
    "positive_prompt": "Detailed English prompt for high quality watercolor or Etegami art style depicting the nostalgic scene...",
    "negative_prompt": "modern technology, dark, depressing, photorealistic, 3D, text, watermark",
    "art_style": "Japanese Watercolor / Etegami (絵手紙・水彩画風)",
    "aspect_ratio": "4:3"
  },
  "postcard_metadata": {
    "headline": "ポストカードの題名（25文字以内）",
    "calligraphy_message": "絵手紙風の短文・俳句調メッセージ（20文字以内）",
    "summary_for_family": "ご家族に向けた温かい様子報告（80文字程度）",
    "recommended_bgm_mood": "autumn" または "sakura" または "windchime" または "winter",
    "stamp_icon": "🍁" または "🌸" または "🌻" または "❄️"
  }
}"""

    prompt = f"""利用者の最近の発話内容:
{conversation_text}

上記の内容を分析し、最適なカテゴリ（思い出・回想または相談事・お悩み）を判定して心温まる水彩画風・絵手紙画像生成用JSONを作成してください:"""

    extracted_payload = None

    # Try local Ollama LLM extraction
    try:
        payload_data = {
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 600
            }
        }
        req = urllib.request.Request(
            f"{config.OLLAMA_URL}/api/generate",
            data=json.dumps(payload_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_reply = data.get("response", "").strip()

            clean_json = raw_reply
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            extracted_payload = json.loads(clean_json)
    except Exception as e:
        print(f"[Multimedia Extraction Notice]: Ollama extraction skipped or timed out ({e}). Using rule-based fallback.")

    # Rule-based fallback if LLM returned invalid JSON
    if not extracted_payload or not isinstance(extracted_payload, dict) or "image_generation_prompt" not in extracted_payload:
        combined_text = " ".join(user_turns)
        consultation_keywords = [
            "心配", "不安", "困った", "どうしよう", "お金", "年金", "税金", "貯金", "相続",
            "手続き", "迷惑", "家族", "寂しい", "痛い", "しんどい", "嫌", "つらい", "愚痴"
        ]
        is_consultation = any(k in combined_text for k in consultation_keywords)

        if is_consultation:
            # Healing artwork for consultation/worries
            extracted_payload = {
                "topic_category": "consultation",
                "consultation_type": "money_or_procedure" if any(k in combined_text for k in ["お金", "年金", "税金", "貯金", "相続"]) else "daily_complaint",
                "privacy_safe_topic": "日々の安心とお気持ちについて",
                "season": detected_season,
                "emotional_transition": {
                    "user_feeling": "心に浮かんだ小さなご心配事",
                    "comforting_goal": "肩の荷が下りる安堵と温もり"
                },
                "image_generation_prompt": {
                    "positive_prompt": "A warm and healing Japanese watercolor painting, Etegami art style. A serene wooden veranda with a steaming cup of green tea, gentle afternoon sunlight, soft shadows, peaceful Japanese garden with blooming wildflowers, atmosphere of comfort and relief, warm pastel colors, masterpiece.",
                    "negative_prompt": "dark, depressing, money, hospital, illness, realistic, text, watermark",
                    "art_style": "Japanese Watercolor / Healing Etegami (癒しの絵手紙・水彩画風)",
                    "aspect_ratio": "4:3",
                    "healing_motif": "teacup_and_sunlight"
                },
                "postcard_metadata": {
                    "headline": "【温もりの便り】ほっと一息、お茶の時間",
                    "calligraphy_message": "肩の力を抜いて のんびり お茶にしましょ",
                    "summary_for_family": "今日はお茶をいただきながら色々なお気持ちをゆっくりお話しされ、ほっと安心されたご様子でした。",
                    "recommended_bgm_mood": "peaceful_ambient",
                    "stamp_icon": "🍵"
                }
            }
        else:
            recent_topic = user_turns[-1] if user_turns else "昔の懐かしい思い出"
            if len(recent_topic) > 25:
                recent_topic = recent_topic[:25] + "…"

            extracted_payload = {
                "topic_category": "childhood_memory",
                "season": detected_season,
                "theme": recent_topic,
                "reminiscence_elements": {
                    "era": "昭和レトロ時代",
                    "location": "校庭やご自宅の縁側",
                    "people_involved": ["家族", "友人"],
                    "food_or_objects": ["お弁当", "季節の味覚"],
                    "emotional_tone": "温かみ、和み、懐かしさ"
                },
                "image_generation_prompt": {
                    "positive_prompt": f"A gentle nostalgic Japanese watercolor painting, Etegami art style. A warm scene in Japan depicting {recent_topic}, soft daylight, nostalgic atmosphere, peaceful family memory, pastel palette, high quality illustration.",
                    "negative_prompt": "modern gadgets, smartphones, photorealistic, 3D render, dark, text, watermark",
                    "art_style": "Japanese Watercolor / Etegami (絵手紙・水彩画風)",
                    "aspect_ratio": "4:3"
                },
                "postcard_metadata": {
                    "headline": f"【思い出の便り】{recent_topic}",
                    "calligraphy_message": "心温まる 懐かしい思い出を 添えて",
                    "summary_for_family": f"本日は「{recent_topic}」について笑顔でお話ししてくださいました。穏やかな気持ちで過ごされています。",
                    "recommended_bgm_mood": detected_season,
                    "stamp_icon": SEASONAL_TEMPLATES[detected_season]["icon"]
                }
            }

    # Attach contextual metadata
    user_record = db.get_user_by_terminal(terminal_id)
    user_name = user_record.get("name", "利用者") if user_record else "利用者"
    extracted_payload["terminal_id"] = terminal_id
    extracted_payload["user_id"] = user_id
    extracted_payload["user_name"] = user_name
    extracted_payload["extracted_at"] = datetime.datetime.now().isoformat()

    # Save into SQLite database
    try:
        db.save_image_prompt_payload(user_id, terminal_id, extracted_payload)
        print(f"[Multimedia Extraction SUCCESS]: Saved image prompt for {terminal_id} (theme: '{extracted_payload.get('theme')}')")
    except Exception as e_db:
        print(f"[Multimedia Extraction DB Error]: {e_db}")

    return extracted_payload

def generate_multimedia_payload(
    user_name: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    season_key: Optional[str] = None,
    terminal_id: Optional[str] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Synthesizes digital postcard metadata and story summary from resident's conversation history
    and chosen/detected seasonal artwork. Incorporates extracted AI image prompt metadata if available.
    Also produces a smartphone-optimized 3-line summary and historical archives.
    """
    # 1. Check for previously extracted AI image prompt payload from DB
    latest_extracted = None
    if terminal_id:
        latest_extracted = db.get_latest_image_prompt_payload(terminal_id=terminal_id)
    if not latest_extracted and user_id:
        latest_extracted = db.get_latest_image_prompt_payload(user_id=user_id)
    
    extracted_data = latest_extracted.get("payload") if latest_extracted else None

    # Determine season
    if not season_key or season_key not in SEASONAL_TEMPLATES:
        if extracted_data and extracted_data.get("season") in SEASONAL_TEMPLATES:
            season_key = extracted_data["season"]
        else:
            season_key = get_current_season()
        
    template = SEASONAL_TEMPLATES[season_key]

    now = datetime.datetime.now()
    reiwa_year = max(1, now.year - 2018)
    formatted_date = f"令和{reiwa_year}年{now.month}月{now.day}日"

    # Dynamic headline & text from AI extraction if present
    if extracted_data and "postcard_metadata" in extracted_data:
        pcm = extracted_data["postcard_metadata"]
        card_title = pcm.get("headline", f"【デジタル絵手紙】{user_name}様の思い出カード")
        calligraphy_text = pcm.get("calligraphy_message", template["calligraphy"])
        summary_text = pcm.get("summary_for_family", "")
        summary_3lines = pcm.get("summary_3lines", "")
        stamp_icon = pcm.get("stamp_icon", template["icon"])
        if pcm.get("date_str"):
            formatted_date = pcm["date_str"]
    else:
        # Fallback to chat history excerpt
        recent_topic = "昔の思い出やお庭の風景"
        if chat_history:
            for msg in reversed(chat_history):
                text = msg.get("message", "").strip()
                if text and len(text) >= 3 and msg.get("sender") == "user":
                    if len(text) > 30:
                        text = text[:30] + "…"
                    recent_topic = text
                    break
        card_title = f"【デジタル絵手紙】{user_name}様の思い出カード"
        calligraphy_text = template["calligraphy"]
        summary_text = (
            f"本日はスタッフやAIとお話しされ、「{recent_topic}」について嬉しそうにお話しされていました。"
            f"穏やかにリラックスしたご様子で過ごされています。"
        )
        summary_3lines = (
            f"【お話の話題】{recent_topic}についての日常対話\n"
            f"【ご本人の様子】AI傾聴パートナーと穏やかに語らい、リラックスされていました\n"
            f"【見守り状況】バイタルや表情もお変わりなく、温かい笑顔でお過ごしです"
        )
        stamp_icon = template["icon"]

    # If summary_3lines not explicitly present, synthesize clean 3-line format
    if not summary_3lines:
        summary_3lines = (
            f"【お話の話題】日常の出来事やお気持ちについて語られました\n"
            f"【ご本人の様子】お声の調子も穏やかで、安心した表情でお話しされていました\n"
            f"【見守り状況】温かい見守りのもと、心地よいリズムでお過ごしです"
        )

    # Determine image URL
    card_image = extracted_data.get("generated_image_url") if extracted_data else None
    if not card_image:
        p_str = str(extracted_data) if extracted_data else ""
        if "喫茶" in p_str or "カフェ" in p_str or "コーヒー" in p_str or "珈琲" in p_str:
            if "教室" in p_str or "文化祭" in p_str or "学園祭" in p_str:
                card_image = "/family/assets/generated_bunkasai.jpg"
            else:
                card_image = "/family/assets/generated_kissaten.jpg"
        elif "文化祭" in p_str or "学園祭" in p_str or "教室" in p_str or "bunkasai" in p_str:
            card_image = "/family/assets/generated_bunkasai.jpg"
        elif "運動会" in p_str or "お弁当" in p_str or "煮物" in p_str or "undoukai" in p_str:
            card_image = "/family/assets/generated_undoukai_bento.jpg"
        elif "友達" in p_str or "お酒" in p_str or "teacup" in p_str or "relaxation_porch" in p_str or "縁側" in p_str:
            card_image = "/family/assets/generated_relaxation_porch.jpg"
        else:
            card_image = template["image_url"]

    # Build historical archives list (past distinct postcards & episodes)
    history_cards = [
        {
            "id": 16,
            "title": "【最新】秋の夕暮れ 心静かに 和",
            "badge": "最新",
            "date_label": "9月9日",
            "short_date": "9/9",
            "date_str": "令和8年9月9日",
            "image_url": "/family/assets/generated_relaxation_porch.jpg",
            "calligraphy": "肩の力を抜いて、ゆっくりと",
            "summary_3lines": (
                "【お話の話題】お友達との付き合い方や、お酒を交えたコミュニケーションについて\n"
                "【ご本人の様子】「相手の表情を気にしてしまう」とお話しされ、次第に表情が和らぎました\n"
                "【見守り状況】温かいお茶の話題で気持ちがほぐれ、穏やかなご様子でお休みになりました"
            ),
            "summary_text": "お友達との付き合い方やお酒の場でのコミュニケーションについてお話しされ、安心されたご様子でした。",
            "stamp_icon": "🍵",
            "season": "autumn"
        },
        {
            "id": 1,
            "title": "【思い出】懐かしの運動会とお弁当",
            "badge": "回想法",
            "date_label": "9月9日",
            "short_date": "9/9",
            "date_str": "令和8年9月9日",
            "image_url": "/family/assets/generated_undoukai_bento.jpg",
            "calligraphy": "家族で囲んだ 懐かしい味",
            "summary_3lines": (
                "【お話の話題】昔懐かしい小学校の運動会と、ご家族で作った手作りお弁当の思い出\n"
                "【ご本人の様子】「おばあちゃんの煮物が美味しかった」と当時の情景を嬉しそうに語られました\n"
                "【見守り状況】回想法を通じてとても生き生きとされ、笑顔あふれる温かい時間となりました"
            ),
            "summary_text": "小学校の頃の運動会や、ご家族で食べた手作りのお弁当の思い出を懐かしく語られました。",
            "stamp_icon": "🍱",
            "season": "autumn"
        },
        {
            "id": 2,
            "title": "【安らぎ】寄り添う小鳥と秋の風",
            "badge": "ヒーリング",
            "date_label": "9月8日",
            "short_date": "9/8",
            "date_str": "令和8年9月8日",
            "image_url": "/family/assets/generated_healing_sparrows.jpg",
            "calligraphy": "心穏やかに 寄り添う日々",
            "summary_3lines": (
                "【お話の話題】庭先を訪れる小鳥や、秋の爽やかな風についての日常会話\n"
                "【ご本人の様子】窓の外の景色を眺めながら、リラックスして相槌を打たれていました\n"
                "【見守り状況】バイタルサインも安定しており、心地よいリズムでお過ごしです"
            ),
            "summary_text": "小鳥のさえずりや庭の景色に心癒され、穏やかな午後を過ごされました。",
            "stamp_icon": "🕊️",
            "season": "autumn"
        },
        {
            "id": 0,
            "title": "【季節の便り】秋の訪れとコスモス庭園",
            "badge": "季節便り",
            "date_label": "9月7日",
            "short_date": "9/7",
            "date_str": "令和8年9月7日",
            "image_url": "/family/assets/sample_postcard.jpg",
            "calligraphy": "おだやかな 秋の日に… お元気で",
            "summary_3lines": (
                "【お話の話題】庭先に咲き始めたコスモスと、秋の心地よい風について\n"
                "【ご本人の様子】「もう秋だね」と目を細め、季節の移ろいを楽しそうにお話しされました\n"
                "【見守り状況】お部屋でゆったりとお茶を楽しまれ、心穏やかにお過ごしです"
            ),
            "summary_text": "庭先に咲くコスモスを眺めながら秋の訪れを楽しまれ、とても穏やかに過ごされています。",
            "stamp_icon": "🍁",
            "season": "autumn"
        }
    ]

    return {
        "card_title": card_title,
        "card_image_url": card_image,
        "card_season": season_key,
        "card_season_name": template["name"],
        "card_icon": stamp_icon,
        "card_calligraphy": calligraphy_text,
        "card_greetings": template["greetings"],
        "card_theme_color": template["accent_color"],
        "bgm_title": template["bgm_title"],
        "bgm_scale_mood": template["scale_mood"],
        "video_title": f"今週の{user_name}様の様子ショートムービー (MP4)",
        "video_duration": "25秒",
        "summary_text": summary_text,
        "summary_3lines": summary_3lines,
        "date_str": formatted_date,
        "stamp_text": "和",
        "history_cards": history_cards,
        "image_generation_prompt": extracted_data.get("image_generation_prompt") if extracted_data else None,
        "reminiscence_elements": extracted_data.get("reminiscence_elements") if extracted_data else None,
        "available_seasons": [
            {
                "key": k,
                "name": v["name"],
                "icon": v["icon"],
                "image_url": v["image_url"],
                "is_current": (k == season_key)
            }
            for k, v in SEASONAL_TEMPLATES.items()
        ]
    }

def modify_or_create_etegami(
    user_id: int,
    terminal_id: str,
    motif_hint: str = "",
    message_hint: str = "",
    season_hint: Optional[str] = None,
    is_completed: bool = False,
    mode: str = "asset_base",
    image_engine: str = "pollinations"
) -> Dict[str, Any]:
    """
    Modifies or generates an Etegami card based on resident's conversational requests
    and past reminiscence / healing conversation history.
    Supports mode="asset_base" (re-using existing assets) and mode="generate_new" (creating novel artworks).
    Allows resident to review draft artwork, adjust motifs/words, and finalize (complete) it.
    """
    now = datetime.datetime.now()
    reiwa_year = max(1, now.year - 2018)
    formatted_date = f"令和{reiwa_year}年{now.month}月{now.day}日"

    combined = f"{motif_hint} {message_hint}".lower()

    # Determine if resident is asking to complete the etegami
    if any(k in combined for k in ["完成", "これでいい", "これで決定", "ばっちり", "気に入った", "送って", "完了"]):
        is_completed = True

    # 1. Check if resident specified an explicit motif or alteration
    explicit_motif = bool(motif_hint and motif_hint.strip())
    motif_candidates = [
        "文化祭", "学園祭", "学校", "高校", "青春", "教室", "映画", "映画館", "シネマ",
        "喫茶店", "喫茶", "純喫茶", "カフェ", "コーヒー", "珈琲",
        "夕焼け", "夕暮れ", "夕日", "夕陽", "縁側", "お茶", "のんびり",
        "小鳥", "雀", "すずめ", "ことり", "運動会", "お弁当", "煮物", "昭和", "昔の思い出",
        "春", "桜", "さくら", "花見", "お花見", "夏", "朝顔", "風鈴", "向日葵", "ひまわり",
        "海", "冬", "雪", "椿", "つばき", "秋", "コスモス", "秋桜", "もみじ", "紅葉"
    ]
    for cand in motif_candidates:
        if cand in combined:
            explicit_motif = True
            break

    base_source = "custom"
    selected_image = None
    theme_title = "【手作り絵手紙】心温まるひととき"
    calligraphy_text = message_hint or "心あたたまる 日々をあなたへ"
    stamp_icon = "和"
    season_key = season_hint or get_current_season()

    ROTATING_PRESETS = [
        {
            "image_url": "/family/assets/generated_relaxation_porch.jpg",
            "theme": "【手作り絵手紙】夕暮れの縁側とお茶",
            "calligraphy": "肩の力を抜いて のんびり お茶にしましょ",
            "stamp_icon": "🍵",
            "season": "autumn",
            "source": "healing"
        },
        {
            "image_url": "/family/assets/generated_kissaten.jpg",
            "theme": "【手作り絵手紙】懐かしの喫茶店と思い出の味",
            "calligraphy": "香り広がる 懐かしいひととき",
            "stamp_icon": "☕",
            "season": "autumn",
            "source": "reminiscence"
        },
        {
            "image_url": "/family/assets/generated_healing_sparrows.jpg",
            "theme": "【手作り絵手紙】寄り添う小鳥の温もり",
            "calligraphy": "心穏やかに 寄り添う日々",
            "stamp_icon": "🕊️",
            "season": "autumn",
            "source": "healing"
        },
        {
            "image_url": "/family/assets/generated_undoukai_bento.jpg",
            "theme": "【手作り絵手紙】懐かしの運動会とお弁当",
            "calligraphy": "家族で囲んだ 懐かしい味",
            "stamp_icon": "🍱",
            "season": "autumn",
            "source": "reminiscence"
        },
        {
            "image_url": "/family/assets/sample_postcard_spring.jpg",
            "theme": "【手作り絵手紙】満開の桜と春爛漫",
            "calligraphy": "春の和みを お届けします",
            "stamp_icon": "🌸",
            "season": "spring",
            "source": "reminiscence"
        },
        {
            "image_url": "/family/assets/sample_postcard.jpg",
            "theme": "【手作り絵手紙】秋の訪れとコスモス庭園",
            "calligraphy": "おだやかな 秋の日に… お元気で",
            "stamp_icon": "🍁",
            "season": "autumn",
            "source": "reminiscence"
        },
        {
            "image_url": "/family/assets/generated_bunkasai.jpg",
            "theme": "【手作り絵手紙】青春の文化祭と思い出",
            "calligraphy": "仲間と創った 懐かしい日々",
            "stamp_icon": "🍁",
            "season": "autumn",
            "source": "reminiscence"
        }
    ]

    # 2. Mode-aware artwork selection or dynamic generation
    clean_motif = re.sub(r'^(?:モチーフ[：:は]?\s*)+', '', motif_hint).strip()
    clean_motif = clean_motif.replace("高校時代の", "").replace("昔の", "").replace("今日の", "").strip()
    clean_motif = re.sub(r'^[「"\'（\(]+|[」"\'）\)]+$', '', clean_motif).strip()
    if clean_motif in ["なし", "特になし", "無", "無し", "モチーフ", "モチーフ:", "モチーフ："]:
        clean_motif = ""

    clean_msg = re.sub(r'^(?:文字|言葉|添え字|メッセージ)[：:は]?\s*', '', message_hint).strip()
    clean_msg = re.sub(r'^[「"\'（\(]+|[」"\'）\)]+$', '', clean_msg).strip()
    if clean_msg in ["なし", "特になし", "無", "無し", "なし）", "なし)", "none", "null"]:
        clean_msg = ""

    if mode == "generate_new":
        # Resident chose to create a completely new artwork without using existing base
        target_motif = clean_motif or "心温まるひととき"
        theme_title = f"【手作り絵手紙】{target_motif}の温もり"
        calligraphy_text = clean_msg or f"心温まる {target_motif}に 思いを添えて"
        stamp_icon = "🎨"
        base_source = "ai_generated_new"
        selected_image = generate_new_etegami_artwork(
            motif=target_motif,
            theme_title=theme_title,
            season=season_key,
            user_id=user_id,
            engine=image_engine
        )
    elif explicit_motif:
        # Resident requested asset_base, check matching existing presets
        if any(k in combined for k in ["黒板", "机", "先生", "授業"]) or ("教室" in combined and not any(k in combined for k in ["文化祭", "学園祭", "喫茶", "カフェ"])):
            selected_image = "/family/assets/generated_classroom.jpg"
            theme_title = "【手作り絵手紙】懐かしの学校の教室と黒板"
            calligraphy_text = message_hint or "黒板に向かい 学び励んだ 青春の日々"
            stamp_icon = "🏫"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["教室", "文化祭", "学園祭", "学校", "高校", "青春"]):
            # Classroom cafe / culture festival
            selected_image = "/family/assets/generated_bunkasai.jpg"
            if any(k in combined for k in ["喫茶", "カフェ", "コーヒー"]):
                theme_title = "【手作り絵手紙】懐かしの教室喫茶と思い出"
                calligraphy_text = message_hint or "仲間と楽しんだ 喫茶の思い出"
            else:
                theme_title = "【手作り絵手紙】青春の文化祭と思い出"
                calligraphy_text = message_hint or "仲間と創った 懐かしい日々"
            stamp_icon = "🍁"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["喫茶店", "喫茶", "純喫茶", "カフェ", "コーヒー", "珈琲", "お茶会"]):
            selected_image = "/family/assets/generated_kissaten.jpg"
            theme_title = "【手作り絵手紙】懐かしの喫茶店と思い出の味"
            calligraphy_text = message_hint or "香り広がる 懐かしいひととき"
            stamp_icon = "☕"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["展覧会", "作品展", "一作展", "絵画展", "美術展"]):
            selected_image = "/family/assets/sample_postcard.jpg"
            theme_title = "【手作り絵手紙】心を込めた作品展の思い出"
            calligraphy_text = message_hint or "彩り豊かな 創作のよろこび"
            stamp_icon = "🎨"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["映画", "映画館", "シネマ", "名画"]):
            selected_image = "/family/assets/sample_postcard.jpg"
            theme_title = "【手作り絵手紙】懐かしの名画と銀幕のひととき"
            calligraphy_text = message_hint or "心躍った あの銀幕の思い出"
            stamp_icon = "🎬"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["夕焼け", "夕暮れ", "夕日", "夕陽", "縁側", "お茶", "のんびり", "porch", "sunset"]):
            selected_image = "/family/assets/generated_relaxation_porch.jpg"
            theme_title = "【手作り絵手紙】夕暮れの縁側とお茶"
            calligraphy_text = message_hint or "肩の力を抜いて のんびり お茶にしましょ"
            stamp_icon = "🍵"
            season_key = "autumn"
            base_source = "healing"
        elif any(k in combined for k in ["小鳥", "雀", "すずめ", "小鳥たち", "寄り添う", "ことり", "sparrow", "bird"]):
            selected_image = "/family/assets/generated_healing_sparrows.jpg"
            theme_title = "【手作り絵手紙】寄り添う小鳥の温もり"
            calligraphy_text = message_hint or "心穏やかに 寄り添う日々"
            stamp_icon = "🕊️"
            season_key = "autumn"
            base_source = "healing"
        elif any(k in combined for k in ["運動会", "お弁当", "煮物", "昭和", "昔の思い出", "家族", "bento"]):
            selected_image = "/family/assets/generated_undoukai_bento.jpg"
            theme_title = "【手作り絵手紙】懐かしの運動会とお弁当"
            calligraphy_text = message_hint or "家族で囲んだ 懐かしい味"
            stamp_icon = "🍱"
            season_key = "autumn"
            base_source = "reminiscence"
        elif any(k in combined for k in ["春", "桜", "さくら", "花見", "お花見", "sakura", "spring"]):
            selected_image = "/family/assets/sample_postcard_spring.jpg"
            theme_title = "【手作り絵手紙】満開の桜と春爛漫"
            calligraphy_text = message_hint or "春の和みを お届けします"
            stamp_icon = "🌸"
            season_key = "spring"
            base_source = "reminiscence"
        elif any(k in combined for k in ["夏", "朝顔", "風鈴", "向日葵", "ひまわり", "海", "summer"]):
            selected_image = "/family/assets/sample_postcard_summer.jpg"
            theme_title = "【手作り絵手紙】涼風の朝顔と風鈴"
            calligraphy_text = message_hint or "夏の涼風 心穏やかに"
            stamp_icon = "🌻"
            season_key = "summer"
            base_source = "reminiscence"
        elif any(k in combined for k in ["冬", "雪", "椿", "つばき", "雪景色", "寒", "winter"]):
            selected_image = "/family/assets/sample_postcard_winter.jpg"
            theme_title = "【手作り絵手紙】紅椿と雪庭の灯り"
            calligraphy_text = message_hint or "健やかに 温かい冬をお過ごしください"
            stamp_icon = "❄️"
            season_key = "winter"
            base_source = "reminiscence"
        elif any(k in combined for k in ["秋", "コスモス", "秋桜", "もみじ", "紅葉", "autumn"]):
            selected_image = "/family/assets/sample_postcard.jpg"
            theme_title = "【手作り絵手紙】秋の訪れとコスモス庭園"
            calligraphy_text = message_hint or "おだやかな 秋の日に… お元気で"
            stamp_icon = "🍁"
            season_key = "autumn"
            base_source = "reminiscence"
        else:
            # Appropriate asset not found for novel motif -> generate dedicated artwork
            target_motif = clean_motif or "心温まるひととき"
            theme_title = f"【手作り絵手紙】{target_motif}の温もり"
            calligraphy_text = clean_msg or f"懐かしい {target_motif}に 思いを馳せて"
            stamp_icon = "🍂"
            base_source = "ai_generated_novel"
            selected_image = generate_new_etegami_artwork(
                motif=target_motif,
                theme_title=theme_title,
                season=season_key,
                user_id=user_id,
                engine=image_engine
            )
    else:
        # Check recent chat history turns from newest to oldest first
        recent_user_msgs = []
        try:
            recent_chats = db.get_chat_history(user_id, limit=25)
            for c in reversed(recent_chats):
                if c.get("sender") == "user":
                    recent_user_msgs.append(c.get("message", "").lower())
        except Exception:
            pass

        for msg in recent_user_msgs:
            if any(k in msg for k in ["黒板", "机", "先生", "授業"]) or ("教室" in msg and not any(k in msg for k in ["文化祭", "学園祭", "喫茶", "カフェ"])):
                selected_image = "/family/assets/generated_classroom.jpg"
                theme_title = "【手作り絵手紙】懐かしの学校の教室と黒板"
                calligraphy_text = message_hint or "黒板に向かい 学び励んだ 青春の日々"
                stamp_icon = "🏫"
                season_key = "autumn"
                base_source = "reminiscence"
                break
            elif any(k in msg for k in ["教室", "文化祭", "学園祭", "学校", "高校", "青春"]):
                selected_image = "/family/assets/generated_bunkasai.jpg"
                if any(k in msg for k in ["喫茶", "カフェ", "コーヒー"]):
                    theme_title = "【手作り絵手紙】懐かしの教室喫茶と思い出"
                    calligraphy_text = message_hint or "仲間と楽しんだ 喫茶の思い出"
                else:
                    theme_title = "【手作り絵手紙】青春の文化祭と思い出"
                    calligraphy_text = message_hint or "仲間と創った 懐かしい日々"
                stamp_icon = "🍁"
                season_key = "autumn"
                base_source = "reminiscence"
                break
            elif any(k in msg for k in ["喫茶店", "喫茶", "純喫茶", "カフェ", "コーヒー", "珈琲", "お茶会"]):
                selected_image = "/family/assets/generated_kissaten.jpg"
                theme_title = "【手作り絵手紙】懐かしの喫茶店と思い出の味"
                calligraphy_text = message_hint or "香り広がる 懐かしいひととき"
                stamp_icon = "☕"
                season_key = "autumn"
                base_source = "reminiscence"
                break
            elif any(k in msg for k in ["桜", "さくら", "花見", "お花見", "春", "入学式"]):
                selected_image = "/family/assets/sample_postcard_spring.jpg"
                theme_title = "【手作り絵手紙】満開の桜と春爛漫"
                calligraphy_text = message_hint or "春の和みを お届けします"
                stamp_icon = "🌸"
                season_key = "spring"
                base_source = "reminiscence"
                break
            elif any(k in msg for k in ["運動会", "お弁当", "煮物", "昭和", "子供の頃", "若い頃", "小学校", "おにぎり"]):
                selected_image = "/family/assets/generated_undoukai_bento.jpg"
                theme_title = "【手作り絵手紙】懐かしの運動会とお弁当"
                calligraphy_text = message_hint or "家族で囲んだ 懐かしい味"
                stamp_icon = "🍱"
                season_key = "autumn"
                base_source = "reminiscence"
                break
            elif any(k in msg for k in ["夕暮れ", "夕焼け", "夕日", "縁側", "お茶", "のんびり", "一息", "休憩", "相談", "悩み", "安心"]):
                selected_image = "/family/assets/generated_relaxation_porch.jpg"
                theme_title = "【手作り絵手紙】夕暮れの縁側とお茶"
                calligraphy_text = message_hint or "肩の力を抜いて のんびり お茶にしましょ"
                stamp_icon = "🍵"
                season_key = "autumn"
                base_source = "healing"
                break
            elif any(k in msg for k in ["小鳥", "すずめ", "雀", "寄り添う", "ことり", "さえずり", "寂しい", "不安", "一人"]):
                selected_image = "/family/assets/generated_healing_sparrows.jpg"
                theme_title = "【手作り絵手紙】寄り添う小鳥の温もり"
                calligraphy_text = message_hint or "心穏やかに 寄り添う日々"
                stamp_icon = "🕊️"
                season_key = "autumn"
                base_source = "healing"
                break

        # 3. If no chat topic matched either, cycle to next distinct preset based on currently displayed artwork
        if not selected_image:
            current_img = ""
            try:
                latest_row = db.get_latest_image_prompt_payload(terminal_id=terminal_id, user_id=user_id)
                if latest_row and latest_row.get("payload"):
                    current_img = latest_row["payload"].get("generated_image_url") or ""
            except Exception:
                pass

            curr_idx = -1
            for idx, p in enumerate(ROTATING_PRESETS):
                if p["image_url"] == current_img:
                    curr_idx = idx
                    break
            
            next_preset = ROTATING_PRESETS[(curr_idx + 1) % len(ROTATING_PRESETS)]
            selected_image = next_preset["image_url"]
            theme_title = next_preset["theme"]
            calligraphy_text = message_hint or next_preset["calligraphy"]
            stamp_icon = next_preset["stamp_icon"]
            season_key = next_preset["season"]
            base_source = next_preset["source"]

    # Failsafe for unassigned image
    if not selected_image:
        template = SEASONAL_TEMPLATES.get(season_key, SEASONAL_TEMPLATES["autumn"])
        selected_image = template["image_url"]
        theme_title = f"【手作り絵手紙】{template['name']}"
        calligraphy_text = message_hint or template["calligraphy"]
        stamp_icon = template["icon"]

    # 4. Completion Status and Family Summaries
    status = "completed" if is_completed else "drafting"
    badge_text = "💮 ご本人様と完成" if is_completed else "🎨 会話をもとに下絵を制作中"

    if is_completed:
        summary_for_family = (
            f"居室端末でこれまでの思い出やお話をもとに下絵を描き、"
            f"ご本人様と一緒に絵や添え字（「{calligraphy_text}」）を確認・手直しして完成させました。"
        )
        summary_3lines = (
            f"【絵手紙制作】{theme_title}（💮 ご本人様と完成）\n"
            f"【添えられた言葉】「{calligraphy_text}」\n"
            f"【ご本人の様子】AIと画面を見ながら楽しそうに手直しされ、納得の笑顔で絵手紙を完成されました"
        )
    else:
        summary_for_family = (
            f"居室端末でこれまでの思い出やお気持ちをもとに下絵を制作し、"
            f"ご本人様と画面を見ながら確認・手直しを行っています。"
        )
        summary_3lines = (
            f"【絵手紙制作】{theme_title}（🎨 下絵を確認・制作中）\n"
            f"【添えられた言葉】「{calligraphy_text}」\n"
            f"【ご本人の様子】AIとお話ししながら、絵手紙のモチーフや文字を楽しそうに相談されています"
        )

    payload = {
        "topic_category": "etegami_creative",
        "season": season_key,
        "theme": theme_title,
        "status": status,
        "is_completed": is_completed,
        "badge_text": badge_text,
        "base_source": base_source,
        "generated_image_url": selected_image,
        "image_generation_prompt": {
            "positive_prompt": f"A gentle nostalgic Japanese watercolor painting, Etegami art style. Depicting {theme_title}, soft sunlight, nostalgic atmosphere, pastel palette, high quality illustration.",
            "negative_prompt": "modern gadgets, smartphones, photorealistic, 3D render, dark, text, watermark",
            "art_style": "Japanese Watercolor / Etegami (絵手紙・水彩画風)",
            "aspect_ratio": "4:3"
        },
        "postcard_metadata": {
            "headline": theme_title,
            "calligraphy_message": calligraphy_text,
            "summary_for_family": summary_for_family,
            "summary_3lines": summary_3lines,
            "stamp_icon": stamp_icon,
            "date_str": formatted_date,
            "is_completed": is_completed,
            "badge_text": badge_text,
            "status": status
        }
    }

    # Determine which engine generated/selected the image
    if base_source in ["ai_generated_novel", "ai_generated_new"] or "generated_custom_etegami_" in (selected_image or ""):
        engine_meta = get_last_used_image_engine()
    elif "sample_postcard" in (selected_image or "") or "generated_" in (selected_image or ""):
        engine_meta = {
            "engine": "preset_archive",
            "name": "季節アーカイブ",
            "type": "preset",
            "desc": "厳選された季節の絵手紙コレクション"
        }
    else:
        engine_meta = get_last_used_image_engine()

    payload["engine"] = engine_meta.get("engine", "local_watercolor")
    payload["engine_name"] = engine_meta.get("name", "自立水彩画 (Local)")
    payload["engine_type"] = engine_meta.get("type", "local")
    payload["engine_desc"] = engine_meta.get("desc", "ローカル水彩画エンジン")

    # Save into DB for persistent access across user, family, and staff
    try:
        user_record = db.get_user_by_terminal(terminal_id)
        user_name = user_record.get("name", "利用者") if user_record else "利用者"
        payload["user_id"] = user_id
        payload["terminal_id"] = terminal_id
        payload["user_name"] = user_name
        payload["extracted_at"] = now.isoformat()
        db.save_image_prompt_payload(user_id, terminal_id, payload)
        print(f"[Etegami Real-Time Update SUCCESS] terminal={terminal_id}, theme='{theme_title}', status='{status}', completed={is_completed}, engine='{engine_meta.get('name')}'")
    except Exception as e:
        print(f"[Etegami Real-Time Update DB Error]: {e}")

    last_notice = get_last_image_gen_notice()
    api_notice_msg = last_notice.get("message") if (last_notice and mode == "generate_new") else None
    if api_notice_msg:
        payload["api_notice"] = api_notice_msg

    return {
        "title": theme_title,
        "theme": theme_title,
        "image_url": selected_image,
        "generated_image_url": selected_image,
        "calligraphy": calligraphy_text,
        "stamp_icon": stamp_icon,
        "season": season_key,
        "date_str": formatted_date,
        "is_completed": is_completed,
        "status": status,
        "badge_text": badge_text,
        "base_source": base_source,
        "engine": engine_meta.get("engine", "local_watercolor"),
        "engine_name": engine_meta.get("name", "自立水彩画 (Local)"),
        "engine_type": engine_meta.get("type", "local"),
        "engine_desc": engine_meta.get("desc", "ローカル水彩画エンジン"),
        "postcard_metadata": payload["postcard_metadata"],
        "api_notice": api_notice_msg,
        "api_error": last_notice if (last_notice and mode == "generate_new") else None
    }


