import os
import math
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = "/media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility"
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "assets/screenshots")
OUTPUT_DIR = os.path.join(BASE_DIR, "assets/manual_images")
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

def draw_badge(draw, text, num_str, x, y, 
               font_size=23, num_font_size=27, circle_size=46,
               bg_color=(15, 23, 42, 245), border_color=(56, 189, 248), 
               num_bg=(56, 189, 248), num_fg=(15, 23, 42)):
    font = get_font(font_size)
    num_font = get_font(num_font_size)
    
    text_bbox = font.getbbox(text)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    
    padding_x = 16
    padding_y = 9
    
    w = circle_size + 14 + tw + padding_x * 2
    h = max(circle_size, th) + padding_y * 2
    
    # Drop shadow
    draw.rounded_rectangle([x + 4, y + 4, x + w + 4, y + h + 4], radius=18, fill=(0, 0, 0, 150))
    # Badge background
    draw.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=bg_color, outline=border_color, width=3)
    
    # Number circle
    cx = x + padding_x
    cy = y + (h - circle_size) // 2
    draw.ellipse([cx, cy, cx + circle_size, cy + circle_size], fill=num_bg)
    
    # Number text centered in circle
    nb = num_font.getbbox(num_str)
    nw = nb[2] - nb[0]
    nh = nb[3] - nb[1]
    draw.text((cx + (circle_size - nw) // 2, cy + (circle_size - nh) // 2 - 2), num_str, fill=num_fg, font=num_font)
    
    # Label text
    draw.text((cx + circle_size + 12, y + (h - th) // 2 - 3), text, fill=(255, 255, 255), font=font)
    return x, y, w, h

def draw_highlight_box(draw, bbox, color=(56, 189, 248), width=4, radius=16):
    draw.rounded_rectangle(bbox, radius=radius, outline=color, width=width)

def draw_arrow(draw, start, end, color=(255, 235, 59), width=5, head_len=20):
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_angle = math.pi / 6
    
    p1 = (x2 - head_len * math.cos(angle - arrow_angle), y2 - head_len * math.sin(angle - arrow_angle))
    p2 = (x2 - head_len * math.cos(angle + arrow_angle), y2 - head_len * math.sin(angle + arrow_angle))
    draw.polygon([end, p1, p2], fill=color)

# ========================================================
# 1. 居室端末（シンプル画面・かんたん画面）
# ========================================================
def generate_simple():
    img = Image.open(os.path.join(SCREENSHOTS_DIR, "resident_room_tablet.png")).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    
    # 1. AI Partner (Gemini Orb) - 🔵 Blue (#2563eb)
    draw_highlight_box(d, [200, 210, 375, 385], color=(37, 99, 235), width=5, radius=88)
    b1_x, b1_y, b1_w, b1_h = draw_badge(
        d, "AIパートナー（ジェミナイさん）", "1", 25, 125,
        font_size=23, num_font_size=27, circle_size=46,
        bg_color=(15, 23, 42, 245), border_color=(96, 165, 250),
        num_bg=(37, 99, 235), num_fg=(255, 255, 255)
    )
    draw_arrow(d, (b1_x + 230, b1_y + b1_h), (265, 210), color=(96, 165, 250), width=5, head_len=18)
    
    # 2. Green Mic Button (Talk button) - 🟠 Orange (#ea580c)
    draw_highlight_box(d, [40, 468, 170, 598], color=(234, 88, 12), width=5, radius=24)
    draw_badge(
        d, "★ みどりのおはなしボタン（ここを押す）", "2", 20, 620,
        font_size=23, num_font_size=27, circle_size=46,
        bg_color=(234, 88, 12, 245), border_color=(255, 255, 255),
        num_bg=(234, 88, 12), num_fg=(255, 255, 255)
    )
    
    # 3. Audio Level Waveform - 🟢 Green (#059669)
    draw_highlight_box(d, [195, 462, 430, 607], color=(5, 150, 105), width=4, radius=18)
    draw_badge(
        d, "声の大きさが見える波形", "3", 200, 400,
        font_size=21, num_font_size=26, circle_size=42,
        bg_color=(15, 23, 42, 240), border_color=(16, 185, 129),
        num_bg=(5, 150, 105), num_fg=(255, 255, 255)
    )
    
    # 4. Speech Recognition Subtitle - 🟣 Purple (#7c3aed)
    draw_highlight_box(d, [615, 440, 1235, 570], color=(124, 58, 237), width=4, radius=18)
    draw_badge(
        d, "お話しした言葉が文字になって出る字幕", "4", 615, 590,
        font_size=23, num_font_size=27, circle_size=46,
        bg_color=(15, 23, 42, 245), border_color=(168, 85, 247),
        num_bg=(124, 58, 237), num_fg=(255, 255, 255)
    )
    
    # 5. Local Guardrail (Mimamori-kun) - 🩵 Sky Blue (#0284c7)
    draw_highlight_box(d, [615, 290, 1235, 345], color=(2, 132, 199), width=4, radius=14)
    draw_badge(
        d, "みまもりくん（危険がないか見守るAI）", "5", 615, 220,
        font_size=23, num_font_size=27, circle_size=46,
        bg_color=(15, 23, 42, 245), border_color=(56, 189, 248),
        num_bg=(2, 132, 199), num_fg=(255, 255, 255)
    )
    
    # 6. Room Badge (Click to switch to detailed) - 🩷 Rose Pink (#e11d48)
    draw_highlight_box(d, [30, 20, 312, 82], color=(225, 29, 72), width=4, radius=25)
    b6_x, b6_y, b6_w, b6_h = draw_badge(
        d, "お部屋番号とお名前（押すとくわしい画面へ）", "6", 330, 24,
        font_size=20, num_font_size=24, circle_size=40,
        bg_color=(15, 23, 42, 245), border_color=(244, 63, 94),
        num_bg=(225, 29, 72), num_fg=(255, 255, 255)
    )
    draw_arrow(d, (330, 52), (312, 52), color=(225, 29, 72), width=4, head_len=14)
    
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUT_DIR, "resident_room_annotated_simple.png")
    out.save(out_path, "PNG")
    print(f"✅ Generated {out_path}")

# ========================================================
# 2. 居室端末（くわしい画面・詳細画面）
# ========================================================
def generate_detailed():
    img = Image.open(os.path.join(SCREENSHOTS_DIR, "resident_room_detailed_tablet.png")).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    
    # 1. Top Status Bar - 🩵 Sky Blue (#0284c7)
    draw_highlight_box(d, [30, 20, 1195, 84], color=(2, 132, 199), width=4, radius=25)
    draw_badge(
        d, "ステータスバー（お部屋・時計・ウォッチ接続・状態）", "1", 30, 95,
        font_size=21, num_font_size=26, circle_size=44,
        bg_color=(15, 23, 42, 245), border_color=(56, 189, 248),
        num_bg=(2, 132, 199), num_fg=(255, 255, 255)
    )
    
    # 2. AI Partner (Gemini Orb) - 🔵 Blue (#2563eb)
    draw_highlight_box(d, [200, 210, 375, 385], color=(37, 99, 235), width=5, radius=88)
    b2_x, b2_y, b2_w, b2_h = draw_badge(
        d, "AIパートナー（ジェミナイさん）", "2", 25, 175,
        font_size=22, num_font_size=26, circle_size=44,
        bg_color=(15, 23, 42, 245), border_color=(96, 165, 250),
        num_bg=(37, 99, 235), num_fg=(255, 255, 255)
    )
    draw_arrow(d, (b2_x + 230, b2_y + b2_h), (265, 210), color=(96, 165, 250), width=5, head_len=18)

    # 3. Green Mic Button (Talk button) - 🟠 Orange (#ea580c)
    draw_highlight_box(d, [40, 468, 170, 598], color=(234, 88, 12), width=5, radius=24)
    draw_badge(
        d, "★ おはなしマイクボタン", "3", 20, 620,
        font_size=22, num_font_size=26, circle_size=44,
        bg_color=(234, 88, 12, 245), border_color=(255, 255, 255),
        num_bg=(234, 88, 12), num_fg=(255, 255, 255)
    )

    # 4. Waveform - 🟢 Green (#059669)
    draw_highlight_box(d, [195, 462, 430, 607], color=(5, 150, 105), width=4, radius=18)
    draw_badge(
        d, "声の大きさが見える波形", "4", 200, 400,
        font_size=21, num_font_size=26, circle_size=42,
        bg_color=(15, 23, 42, 240), border_color=(16, 185, 129),
        num_bg=(5, 150, 105), num_fg=(255, 255, 255)
    )

    # 5. User Speech Subtitle box (Left) - 🔷 Cyan/Teal (#0891b2)
    draw_highlight_box(d, [615, 440, 915, 580], color=(8, 145, 178), width=4, radius=16)
    draw_badge(
        d, "あなたの声（認識字幕）", "5", 605, 595,
        font_size=19, num_font_size=24, circle_size=40,
        bg_color=(15, 23, 42, 245), border_color=(6, 182, 212),
        num_bg=(8, 145, 178), num_fg=(255, 255, 255)
    )

    # 6. Gemini Response Subtitle box (Right) - 🟢 Emerald (#10b981)
    draw_highlight_box(d, [930, 440, 1235, 580], color=(16, 185, 129), width=4, radius=16)
    draw_badge(
        d, "Geminiのお返事字幕", "6", 930, 595,
        font_size=19, num_font_size=24, circle_size=40,
        bg_color=(15, 23, 42, 245), border_color=(52, 211, 153),
        num_bg=(16, 185, 129), num_fg=(255, 255, 255)
    )

    # 7. Local Guardrail Banner (Top right) - 🟣 Purple (#7c3aed)
    draw_highlight_box(d, [615, 285, 1235, 365], color=(124, 58, 237), width=4, radius=14)
    draw_badge(
        d, "みまもりくん（安全見守り・プライバシー監視）", "7", 615, 215,
        font_size=21, num_font_size=26, circle_size=42,
        bg_color=(15, 23, 42, 245), border_color=(168, 85, 247),
        num_bg=(124, 58, 237), num_fg=(255, 255, 255)
    )

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUT_DIR, "resident_room_annotated_detailed.png")
    out.save(out_path, "PNG")
    print(f"✅ Generated {out_path}")

# ========================================================
# 3. 介護スタッフステーション: staff_dashboard_annotated.png
# ========================================================
def generate_staff():
    img = Image.open(os.path.join(SCREENSHOTS_DIR, "staff_dashboard.png")).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Sidebar - Blue #2563eb
    draw_highlight_box(d, [2, 2, 260, 898], color=(37, 99, 235), width=4, radius=12)
    draw_badge(d, "業務メニュー", "1", 16, 20,
               font_size=19, num_font_size=25, circle_size=42,
               border_color=(37, 99, 235), num_bg=(37, 99, 235), num_fg=(255, 255, 255))

    # 2. Alert Banner - Red #ef4444
    draw_highlight_box(d, [290, 102, 1410, 292], color=(239, 68, 68), width=4, radius=16)
    draw_badge(d, "緊急アクティブアラート（SOS・転倒検知）", "2", 450, 46,
               font_size=19, num_font_size=25, circle_size=42,
               border_color=(239, 68, 68), num_bg=(239, 68, 68), num_fg=(255, 255, 255))

    # 3. Google Fit Sync - Orange #ea580c (Placed in empty right-middle space of the card)
    draw_highlight_box(d, [290, 312, 1410, 422], color=(234, 88, 12), width=4, radius=16)
    draw_badge(d, "Google Fit クラウド自動同期", "3", 740, 338,
               font_size=18, num_font_size=24, circle_size=40,
               border_color=(234, 88, 12), num_bg=(234, 88, 12), num_fg=(255, 255, 255))

    # 4. Recent Vitals - Green #059669 (Placed in empty header space next to title)
    draw_highlight_box(d, [290, 442, 840, 884], color=(5, 150, 105), width=4, radius=16)
    draw_badge(d, "リアルタイムバイタル一覧", "4", 545, 450,
               font_size=18, num_font_size=24, circle_size=40,
               border_color=(5, 150, 105), num_bg=(5, 150, 105), num_fg=(255, 255, 255))

    # 5. Conversation Summary & AI Notes - Purple #7c3aed (Placed in empty header space next to title)
    draw_highlight_box(d, [860, 442, 1410, 884], color=(124, 58, 237), width=4, radius=16)
    draw_badge(d, "AIカルテ支援（会話要約）", "5", 1060, 450,
               font_size=18, num_font_size=24, circle_size=40,
               border_color=(124, 58, 237), num_bg=(124, 58, 237), num_fg=(255, 255, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(os.path.join(OUTPUT_DIR, "staff_dashboard_annotated.png"), "PNG")
    print("✅ Created staff_dashboard_annotated.png")

# ========================================================
# 4-1. ご家族ポータル (PC版・上部画面): family_portal_pc_top_annotated.png
# ========================================================
def generate_family_pc_top():
    img_full = Image.open(os.path.join(SCREENSHOTS_DIR, "family_portal_pc_etegami.png")).convert("RGBA")
    # Crop cleanly to archive bar bottom (y: 0 to 695)
    img = img_full.crop((0, 0, 1440, 695))
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Resident Health Summary - 🔵 Blue (#2563eb)
    draw_highlight_box(d, [140, 103, 1300, 259], color=(37, 99, 235), width=4, radius=16)
    draw_badge(d, "入居者様の最新体調サマリー（体温・血圧・ご機嫌の様子）", "1", 160, 60,
               font_size=21, num_font_size=26, circle_size=44,
               border_color=(37, 99, 235), num_bg=(37, 99, 235), num_fg=(255, 255, 255))

    # 2. Intercom - 🟠 Orange (#ea580c)
    draw_highlight_box(d, [140, 268, 1300, 480], color=(234, 88, 12), width=4, radius=16)
    draw_badge(d, "居室直通インターホン（ワンタップで居室タブレットへ音声通話）", "2", 160, 220,
               font_size=21, num_font_size=26, circle_size=44,
               border_color=(234, 88, 12), num_bg=(234, 88, 12), num_fg=(255, 255, 255))

    # 3. Feature Tabs - 🟢 Green (#059669)
    draw_highlight_box(d, [140, 525, 1300, 595], color=(5, 150, 105), width=4, radius=14)
    draw_badge(d, "機能切り替えタブ（絵手紙・バイタル推移・面会予約・ショート動画）", "3", 160, 475,
               font_size=20, num_font_size=25, circle_size=42,
               border_color=(5, 150, 105), num_bg=(5, 150, 105), num_fg=(255, 255, 255))

    # 4. Archive Bar - 🟣 Purple (#7c3aed)
    draw_highlight_box(d, [140, 610, 1300, 680], color=(124, 58, 237), width=4, radius=14)
    draw_badge(d, "過去のご様子・絵手紙アーカイブ（過去の日付を選択して振り返り）", "4", 160, 600,
               font_size=20, num_font_size=25, circle_size=42,
               border_color=(124, 58, 237), num_bg=(124, 58, 237), num_fg=(255, 255, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUT_DIR, "family_portal_pc_top_annotated.png")
    final.save(out_path, "PNG")
    print(f"✅ Created {out_path}")

# ========================================================
# 4-2. ご家族ポータル (PC版・下部画面): family_portal_pc_bottom_annotated.png
# ========================================================
def generate_family_pc_bottom():
    img_full = Image.open(os.path.join(SCREENSHOTS_DIR, "family_portal_pc_etegami.png")).convert("RGBA")
    # Crop bottom part cleanly (y: 690 to 1640)
    img = img_full.crop((0, 690, 1440, 1640))
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Season buttons - 🟠 Orange (#ea580c)
    draw_highlight_box(d, [735, 80, 1180, 140], color=(234, 88, 12), width=4, radius=12)
    draw_badge(d, "四季の着せ替えボタン（秋・春・夏・冬）", "1", 740, 25,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(234, 88, 12), num_bg=(234, 88, 12), num_fg=(255, 255, 255))

    # 2. Watercolor Card - 🩷 Rose Pink (#e11d48)
    draw_highlight_box(d, [730, 150, 1275, 605], color=(225, 29, 72), width=4, radius=16)
    draw_badge(d, "昭和レトロ水彩画（本日の会話からAIが描いた絵手紙）", "2", 740, 100,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(225, 29, 72), num_bg=(225, 29, 72), num_fg=(255, 255, 255))

    # 3. Print & Save Buttons - 🔵 Blue (#2563eb)
    draw_highlight_box(d, [840, 640, 1255, 695], color=(37, 99, 235), width=4, radius=10)
    draw_badge(d, "絵手紙の画像保存 ＆ ハガキ印刷（アルバム保管用）", "3", 740, 645,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(37, 99, 235), num_bg=(37, 99, 235), num_fg=(255, 255, 255))

    # 4. BGM Player - 🟢 Green (#059669)
    draw_highlight_box(d, [730, 730, 1275, 810], color=(5, 150, 105), width=4, radius=12)
    draw_badge(d, "和風アンビエントBGM再生（癒しの琴・笛の音色）", "4", 740, 825,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(5, 150, 105), num_bg=(5, 150, 105), num_fg=(255, 255, 255))

    # 5. AI Conversation Episode - 🟣 Purple (#7c3aed)
    draw_highlight_box(d, [140, 20, 700, 885], color=(124, 58, 237), width=4, radius=14)
    draw_badge(d, "本日のAI会話エピソード（3行サマリー ＆ 会話ログ）", "5", 150, 35,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(124, 58, 237), num_bg=(124, 58, 237), num_fg=(255, 255, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUT_DIR, "family_portal_pc_bottom_annotated.png")
    final.save(out_path, "PNG")
    print(f"✅ Created {out_path}")

# ========================================================
# 4-3. ご家族ポータル (スマホ版): family_portal_mobile_annotated.png
# ========================================================
def generate_family_mobile():
    img = Image.open(os.path.join(SCREENSHOTS_DIR, "family_portal_mobile.png")).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Health status card - 🔵 Blue (#2563eb)
    draw_highlight_box(d, [20, 106, 376, 449], color=(37, 99, 235), width=3, radius=14)
    draw_badge(d, "体調サマリー（体温・血圧・ご機嫌）", "1", 20, 60,
               font_size=15, num_font_size=19, circle_size=32,
               border_color=(37, 99, 235), num_bg=(37, 99, 235), num_fg=(255, 255, 255))

    # 2. Intercom card - 🟠 Orange (#ea580c)
    draw_highlight_box(d, [20, 450, 376, 779], color=(234, 88, 12), width=3, radius=14)
    draw_badge(d, "居室直通インターホン通話", "2", 20, 410,
               font_size=15, num_font_size=19, circle_size=32,
               border_color=(234, 88, 12), num_bg=(234, 88, 12), num_fg=(255, 255, 255))

    # 3. Tabs - 🟢 Green (#059669)
    draw_highlight_box(d, [20, 825, 376, 895], color=(5, 150, 105), width=3, radius=10)
    draw_badge(d, "メニュータブ（絵手紙・バイタル）", "3", 20, 785,
               font_size=15, num_font_size=19, circle_size=32,
               border_color=(5, 150, 105), num_bg=(5, 150, 105), num_fg=(255, 255, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = os.path.join(OUTPUT_DIR, "family_portal_mobile_annotated.png")
    final.save(out_path, "PNG")
    print(f"✅ Created {out_path}")

# ========================================================
# 5. 訪問理容・美容師モード: barber_mode_annotated.png
# ========================================================
def generate_barber():
    img = Image.open(os.path.join(SCREENSHOTS_DIR, "barber_mode_dashboard.png")).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Appointment Card
    draw_highlight_box(d, [20, 80, 480, 305], color=(56, 189, 248), width=4, radius=12)
    draw_badge(d, "本日の施術予約カード（居室番号・お名前・メニュー）", "1", 20, 25,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(56, 189, 248), num_bg=(56, 189, 248), num_fg=(15, 23, 42))

    # 2. Yellow Caution Note
    draw_highlight_box(d, [30, 185, 470, 232], color=(234, 179, 8), width=4, radius=8)
    draw_badge(d, "⚠️【最重要】姿勢・認知症の注意点（施術前必読）", "2", 30, 135,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(234, 179, 8), num_bg=(234, 179, 8), num_fg=(0, 0, 0))

    # 3. Report Button
    draw_highlight_box(d, [30, 240, 145, 290], color=(16, 185, 129), width=4, radius=8)
    draw_badge(d, "施術完了報告ボタン（カルテ・家族へ即座に共有）", "3", 160, 240,
               font_size=21, num_font_size=26, circle_size=42,
               border_color=(16, 185, 129), num_bg=(16, 185, 129), num_fg=(255, 255, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(os.path.join(OUTPUT_DIR, "barber_mode_annotated.png"), "PNG")
    print("✅ Created barber_mode_annotated.png")

if __name__ == "__main__":
    generate_simple()
    generate_detailed()
    generate_staff()
    generate_family_pc_top()
    generate_family_pc_bottom()
    generate_family_mobile()
    generate_barber()
    print("🎉 All annotated manual images generated successfully!")
