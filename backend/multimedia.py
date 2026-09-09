"""
backend/multimedia.py - Care-Link Multimedia & Digital Postcard Generation Engine.
Implements Option 1: High-definition seasonal artwork + AI-assisted conversation synthesis.
Clean provider architecture ready for future external image AI (Imagen 3 / DALL-E 3) if activated.
"""

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

import urllib.request
import json
import time
from backend import config, database as db

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
    terminal_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesizes digital postcard metadata and story summary from resident's conversation history
    and chosen/detected seasonal artwork. Incorporates extracted AI image prompt metadata if available.
    """
    # 1. Check for previously extracted AI image prompt payload from DB
    latest_extracted = None
    if terminal_id:
        latest_extracted = db.get_latest_image_prompt_payload(terminal_id=terminal_id)
    
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
        stamp_icon = pcm.get("stamp_icon", template["icon"])
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
        stamp_icon = template["icon"]

    card_image = extracted_data.get("generated_image_url", template["image_url"]) if extracted_data else template["image_url"]

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
        "date_str": formatted_date,
        "stamp_text": "和",
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
