import os
import subprocess

BASE_DIR = "/media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility"
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "assets/screenshots")
OUTPUT_DIR = os.path.join(BASE_DIR, "assets/manual_images")
TEMP_HTML_DIR = os.path.join(BASE_DIR, "assets/manual_images/temp_html")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_HTML_DIR, exist_ok=True)

def render_annotated_image(html_filename, output_png, width, height, html_content):
    html_path = os.path.join(TEMP_HTML_DIR, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    out_path = os.path.join(OUTPUT_DIR, output_png)
    cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--window-size={width},{height}",
        "--virtual-time-budget=3000",
        f"--screenshot={out_path}",
        f"file://{html_path}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✅ Generated {output_png} ({width}x{height})")
    else:
        print(f"❌ Error generating {output_png}: {res.stderr}")

# ----------------------------------------------------
# 1. 居室端末（シンプル画面）: resident_room_annotated_simple.png
# ----------------------------------------------------
html_simple = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 1280px; height: 800px; position: relative; overflow: hidden; background: #000; }}
  .bg {{ width: 1280px; height: 800px; display: block; }}
  .overlay {{ position: absolute; top: 0; left: 0; width: 1280px; height: 800px; pointer-events: none; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.95);
    color: #fff;
    font-size: 15px;
    font-weight: 800;
    padding: 7px 14px;
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    border: 2px solid #38bdf8;
    z-index: 10;
  }}
  .badge-num {{
    background: #38bdf8;
    color: #0f172a;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 14px;
  }}
  .badge.orange {{ border-color: #ea580c; }}
  .badge.orange .badge-num {{ background: #ea580c; color: #fff; }}
  .badge.green {{ border-color: #10b981; }}
  .badge.green .badge-num {{ background: #10b981; color: #fff; }}
  .badge.purple {{ border-color: #a855f7; }}
  .badge.purple .badge-num {{ background: #a855f7; color: #fff; }}

  .box-highlight {{
    position: absolute;
    border: 3.5px dashed #38bdf8;
    border-radius: 16px;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.5);
  }}
  .box-highlight.orange {{ border-color: #ea580c; box-shadow: 0 0 14px rgba(234, 88, 12, 0.6); }}
  .box-highlight.green {{ border-color: #10b981; box-shadow: 0 0 14px rgba(16, 185, 129, 0.5); }}
  .box-highlight.purple {{ border-color: #a855f7; box-shadow: 0 0 14px rgba(168, 85, 247, 0.5); }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/resident_room_tablet.png">

  <!-- Highlight Boxes -->
  <!-- 1. Room Badge -->
  <div class="box-highlight" style="top: 25px; left: 35px; width: 210px; height: 75px; border-radius: 35px;"></div>
  <!-- 2. Mic Button -->
  <div class="box-highlight orange" style="top: 590px; left: 35px; width: 95px; height: 95px; border-radius: 50%;"></div>
  <!-- 3. Waveform Box -->
  <div class="box-highlight" style="top: 580px; left: 150px; width: 260px; height: 175px;"></div>
  <!-- 4. Local AI Guard -->
  <div class="box-highlight green" style="top: 360px; left: 485px; width: 480px; height: 68px;"></div>
  <!-- 5. Subtitle Display Box -->
  <div class="box-highlight purple" style="top: 550px; left: 485px; width: 480px; height: 155px;"></div>

  <!-- Badges -->
  <div class="badge" style="top: 110px; left: 35px;">
    <span class="badge-num">1</span>
    <span>お部屋番号とお名前（押すと詳細画面へ切替）</span>
  </div>

  <div class="badge orange" style="top: 535px; left: 30px; font-size: 15px; padding: 7px 15px;">
    <span class="badge-num">2</span>
    <span>★ マイクボタン（ここを押してお話しする）</span>
  </div>

  <div class="badge" style="top: 535px; left: 170px;">
    <span class="badge-num">3</span>
    <span>声の大きさが見える波形</span>
  </div>

  <div class="badge green" style="top: 310px; left: 490px;">
    <span class="badge-num">4</span>
    <span>みまもりくん（危険や異変がないか見守るAI）</span>
  </div>

  <div class="badge purple" style="top: 715px; left: 490px;">
    <span class="badge-num">5</span>
    <span>お話しした言葉が文字になって出る字幕ボックス</span>
  </div>
</body>
</html>
"""
render_annotated_image("resident_simple.html", "resident_room_annotated_simple.png", 1280, 800, html_simple)

# ----------------------------------------------------
# 2. 居室端末（詳細画面）: resident_room_annotated_detailed.png
# ----------------------------------------------------
html_detailed = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 1280px; height: 800px; position: relative; overflow: hidden; background: #000; }}
  .bg {{ width: 1280px; height: 800px; display: block; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.95);
    color: #fff;
    font-size: 14px;
    font-weight: 700;
    padding: 6px 12px;
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    border: 2px solid #38bdf8;
    z-index: 10;
  }}
  .badge-num {{
    background: #38bdf8;
    color: #0f172a;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 13px;
  }}
  .badge.orange {{ border-color: #ea580c; }}
  .badge.orange .badge-num {{ background: #ea580c; color: #fff; }}
  .badge.emerald {{ border-color: #10b981; }}
  .badge.emerald .badge-num {{ background: #10b981; color: #fff; }}

  .box-highlight {{
    position: absolute;
    border: 3px dashed #38bdf8;
    border-radius: 16px;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
  }}
  .box-highlight.orange {{ border-color: #ea580c; box-shadow: 0 0 12px rgba(234, 88, 12, 0.5); }}
  .box-highlight.emerald {{ border-color: #10b981; box-shadow: 0 0 12px rgba(16, 185, 129, 0.5); }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/resident_room_detailed_tablet.png">

  <!-- Boxes -->
  <!-- 1. Top Badges (Debug & Status) -->
  <div class="box-highlight" style="top: 25px; left: 35px; width: 895px; height: 75px; border-radius: 35px;"></div>
  <!-- 2. Mic Button -->
  <div class="box-highlight orange" style="top: 590px; left: 35px; width: 95px; height: 95px; border-radius: 50%;"></div>
  <!-- 3. User Speech Box -->
  <div class="box-highlight" style="top: 565px; left: 485px; width: 230px; height: 155px;"></div>
  <!-- 4. Gemini Response Box -->
  <div class="box-highlight emerald" style="top: 565px; left: 730px; width: 235px; height: 155px;"></div>

  <!-- Badges -->
  <div class="badge" style="top: 110px; left: 45px;">
    <span class="badge-num">1</span>
    <span>上部バー（部屋名・時計・ウォッチ接続・Gemini Live状態）</span>
  </div>

  <div class="badge orange" style="top: 535px; left: 35px;">
    <span class="badge-num">2</span>
    <span>AI音声対話マイク</span>
  </div>

  <div class="badge" style="top: 515px; left: 490px;">
    <span class="badge-num">3</span>
    <span>あなたの声（音声認識字幕）</span>
  </div>

  <div class="badge emerald" style="top: 515px; left: 735px;">
    <span class="badge-num">4</span>
    <span>Geminiのお返事テキスト字幕</span>
  </div>
</body>
</html>
"""
render_annotated_image("resident_detailed.html", "resident_room_annotated_detailed.png", 1280, 800, html_detailed)

# ----------------------------------------------------
# 3. 介護スタッフステーション: staff_dashboard_annotated.png
# ----------------------------------------------------
html_staff = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 1440px; height: 900px; position: relative; overflow: hidden; background: #000; }}
  .bg {{ width: 1440px; height: 900px; display: block; }}
  .overlay {{ position: absolute; top: 0; left: 0; width: 1440px; height: 900px; pointer-events: none; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(15, 23, 42, 0.94);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    padding: 7px 14px;
    border-radius: 8px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.6);
    border: 2px solid #38bdf8;
    z-index: 10;
  }}
  .badge-num {{
    background: #38bdf8;
    color: #0f172a;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 14px;
  }}
  .badge.red {{ border-color: #ef4444; }}
  .badge.red .badge-num {{ background: #ef4444; color: #fff; }}
  .badge.green {{ border-color: #10b981; }}
  .badge.green .badge-num {{ background: #10b981; color: #fff; }}
  .badge.purple {{ border-color: #a855f7; }}
  .badge.purple .badge-num {{ background: #a855f7; color: #fff; }}

  .box-highlight {{
    position: absolute;
    border: 3px dashed #38bdf8;
    border-radius: 12px;
    box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
  }}
  .box-highlight.red {{ border-color: #ef4444; box-shadow: 0 0 15px rgba(239, 68, 68, 0.5); }}
  .box-highlight.green {{ border-color: #10b981; box-shadow: 0 0 15px rgba(16, 185, 129, 0.4); }}
  .box-highlight.purple {{ border-color: #a855f7; box-shadow: 0 0 15px rgba(168, 85, 247, 0.4); }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/staff_dashboard.png">

  <!-- Highlight Boxes -->
  <!-- 1. Alert Banner -->
  <div class="box-highlight red" style="top: 75px; left: 240px; width: 960px; height: 65px;"></div>
  <!-- 2. Room Matrix -->
  <div class="box-highlight" style="top: 155px; left: 240px; width: 560px; height: 360px;"></div>
  <!-- 3. Vital Table -->
  <div class="box-highlight green" style="top: 530px; left: 240px; width: 1160px; height: 350px;"></div>
  <!-- 4. Quick Actions / Broadcast -->
  <div class="box-highlight purple" style="top: 155px; left: 820px; width: 580px; height: 360px;"></div>

  <!-- Badges -->
  <div class="badge red" style="top: 40px; left: 250px;">
    <span class="badge-num">1</span>
    <span>緊急SOS・転倒検知アラート通知バー（全画面赤色警報・即座に応答）</span>
  </div>

  <div class="badge" style="top: 170px; left: 260px;">
    <span class="badge-num">2</span>
    <span>全居室見守りマトリクス（在室・呼出・対話状況を一目で把握）</span>
  </div>

  <div class="badge purple" style="top: 170px; left: 840px;">
    <span class="badge-num">3</span>
    <span>構内一斉放送マイク ＆ AIカルテ・日報ドラフト自動生成</span>
  </div>

  <div class="badge green" style="top: 545px; left: 260px;">
    <span class="badge-num">4</span>
    <span>リアルタイムバイタル記録テーブル（心拍数・SpO2・体温の秒単位監視）</span>
  </div>
</body>
</html>
"""
render_annotated_image("staff_dashboard.html", "staff_dashboard_annotated.png", 1440, 900, html_staff)

# ----------------------------------------------------
# 4. ご家族ポータル (PC絵手紙): family_portal_pc_annotated.png
# ----------------------------------------------------
html_family_pc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 1440px; height: 1650px; position: relative; overflow: hidden; background: #faf8f5; }}
  .bg {{ width: 1440px; height: 1650px; display: block; }}
  .overlay {{ position: absolute; top: 0; left: 0; width: 1440px; height: 1650px; pointer-events: none; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.94);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    padding: 8px 16px;
    border-radius: 24px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
    border: 2px solid #e11d48;
    z-index: 10;
  }}
  .badge-num {{
    background: #e11d48;
    color: #fff;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 14px;
  }}
  .badge.orange {{ border-color: #ea580c; }}
  .badge.orange .badge-num {{ background: #ea580c; }}
  .badge.blue {{ border-color: #2563eb; }}
  .badge.blue .badge-num {{ background: #2563eb; }}
  .badge.emerald {{ border-color: #059669; }}
  .badge.emerald .badge-num {{ background: #059669; }}

  .box-highlight {{
    position: absolute;
    border: 3.5px dashed #e11d48;
    border-radius: 16px;
    box-shadow: 0 0 15px rgba(225, 29, 72, 0.35);
  }}
  .box-highlight.blue {{ border-color: #2563eb; box-shadow: 0 0 15px rgba(37, 99, 235, 0.35); }}
  .box-highlight.orange {{ border-color: #ea580c; box-shadow: 0 0 15px rgba(234, 88, 12, 0.35); }}
  .box-highlight.emerald {{ border-color: #059669; box-shadow: 0 0 15px rgba(5, 150, 105, 0.35); }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/family_portal_pc_etegami.png">

  <!-- Boxes -->
  <!-- 1. Resident Summary & Intercom -->
  <div class="box-highlight blue" style="top: 70px; left: 140px; width: 1160px; height: 215px;"></div>
  <!-- 2. AI Conversation Episode -->
  <div class="box-highlight orange" style="top: 390px; left: 140px; width: 550px; height: 530px;"></div>
  <!-- 3. Digital Postcard Artwork -->
  <div class="box-highlight" style="top: 390px; left: 720px; width: 580px; height: 1120px;"></div>
  <!-- 4. Season Bar -->
  <div class="box-highlight" style="top: 485px; left: 745px; width: 530px; height: 55px; border-style: dotted;"></div>
  <!-- 5. Action Buttons -->
  <div class="box-highlight" style="top: 1375px; left: 745px; width: 530px; height: 60px; border-style: dotted;"></div>
  <!-- 6. BGM Player -->
  <div class="box-highlight emerald" style="top: 1445px; left: 745px; width: 530px; height: 65px;"></div>

  <!-- Badges -->
  <div class="badge blue" style="top: 45px; left: 160px;">
    <span class="badge-num">1</span>
    <span>入居者様の最新体調 ＆ 居室直通インターホン通話ボタン</span>
  </div>

  <div class="badge orange" style="top: 360px; left: 160px;">
    <span class="badge-num">2</span>
    <span>本日のAI会話エピソード（対話サマリー ＆ 会話の1コマ）</span>
  </div>

  <div class="badge" style="top: 360px; left: 740px;">
    <span class="badge-num">3</span>
    <span>昭和レトロ水彩画風「デジタル絵手紙」カード</span>
  </div>

  <div class="badge" style="top: 450px; right: 170px; font-size: 14px; padding: 6px 12px;">
    <span class="badge-num" style="width:20px; height:20px; font-size:12px;">4</span>
    <span>四季の切り替え（秋・春・夏・冬）</span>
  </div>

  <div class="badge" style="top: 1340px; right: 170px; font-size: 14px; padding: 6px 12px;">
    <span class="badge-num" style="width:20px; height:20px; font-size:12px;">5</span>
    <span>絵手紙の画像保存 ＆ ハガキ印刷</span>
  </div>

  <div class="badge emerald" style="top: 1520px; right: 170px; font-size: 14px; padding: 6px 12px;">
    <span class="badge-num" style="width:20px; height:20px; font-size:12px;">6</span>
    <span>和風アンビエントBGM再生</span>
  </div>
</body>
</html>
"""
render_annotated_image("family_pc.html", "family_portal_pc_annotated.png", 1440, 1650, html_family_pc)

# ----------------------------------------------------
# 5. ご家族ポータル (スマホ): family_portal_mobile_annotated.png
# ----------------------------------------------------
html_family_mobile = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 412px; height: 915px; position: relative; overflow: hidden; background: #faf8f5; }}
  .bg {{ width: 412px; height: 915px; display: block; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(30, 41, 59, 0.94);
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    padding: 5px 10px;
    border-radius: 16px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.25);
    border: 1.5px solid #e11d48;
    z-index: 10;
  }}
  .badge-num {{
    background: #e11d48;
    color: #fff;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 11px;
  }}
  .badge.blue {{ border-color: #2563eb; }}
  .badge.blue .badge-num {{ background: #2563eb; }}
  .badge.orange {{ border-color: #ea580c; }}
  .badge.orange .badge-num {{ background: #ea580c; }}

  .box-highlight {{
    position: absolute;
    border: 2.5px dashed #e11d48;
    border-radius: 12px;
    box-shadow: 0 0 10px rgba(225, 29, 72, 0.35);
  }}
  .box-highlight.blue {{ border-color: #2563eb; }}
  .box-highlight.orange {{ border-color: #ea580c; }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/family_portal_mobile.png">

  <!-- Boxes -->
  <div class="box-highlight blue" style="top: 60px; left: 15px; width: 382px; height: 180px;"></div>
  <div class="box-highlight orange" style="top: 250px; left: 15px; width: 382px; height: 50px;"></div>
  <div class="box-highlight" style="top: 360px; left: 15px; width: 382px; height: 260px;"></div>

  <!-- Badges -->
  <div class="badge blue" style="top: 40px; left: 25px;">
    <span class="badge-num">1</span>
    <span>体調ステータス ＆ 居室直通通話ボタン</span>
  </div>

  <div class="badge orange" style="top: 305px; left: 25px;">
    <span class="badge-num">2</span>
    <span>タブ切り替え（絵手紙・バイタル・面会予約）</span>
  </div>

  <div class="badge" style="top: 625px; left: 25px;">
    <span class="badge-num">3</span>
    <span>今日のご様子 ＆ 会話ダイジェスト</span>
  </div>
</body>
</html>
"""
render_annotated_image("family_mobile.html", "family_portal_mobile_annotated.png", 412, 915, html_family_mobile)

# ----------------------------------------------------
# 6. 訪問理容・美容師モード: barber_mode_annotated.png
# ----------------------------------------------------
html_barber = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Noto Sans CJK JP', sans-serif; }}
  body {{ width: 1280px; height: 800px; position: relative; overflow: hidden; background: #000; }}
  .bg {{ width: 1280px; height: 800px; display: block; }}
  
  .badge {{
    position: absolute;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(15, 23, 42, 0.94);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    padding: 8px 16px;
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    border: 2px solid #38bdf8;
    z-index: 10;
  }}
  .badge-num {{
    background: #38bdf8;
    color: #0f172a;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 14px;
  }}
  .badge.yellow {{ border-color: #eab308; }}
  .badge.yellow .badge-num {{ background: #eab308; color: #000; }}
  .badge.green {{ border-color: #10b981; }}
  .badge.green .badge-num {{ background: #10b981; color: #fff; }}

  .box-highlight {{
    position: absolute;
    border: 3.5px dashed #38bdf8;
    border-radius: 12px;
    box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
  }}
  .box-highlight.yellow {{ border-color: #eab308; box-shadow: 0 0 15px rgba(234, 179, 8, 0.5); }}
  .box-highlight.green {{ border-color: #10b981; box-shadow: 0 0 15px rgba(16, 185, 129, 0.5); }}
</style>
</head>
<body>
  <img class="bg" src="{SCREENSHOTS_DIR}/barber_mode_dashboard.png">

  <!-- Boxes -->
  <!-- 1. Appointment Card -->
  <div class="box-highlight" style="top: 105px; left: 20px; width: 610px; height: 280px;"></div>
  <!-- 2. Warning Note -->
  <div class="box-highlight yellow" style="top: 240px; left: 30px; width: 590px; height: 58px;"></div>
  <!-- 3. Report Button -->
  <div class="box-highlight green" style="top: 300px; left: 35px; width: 150px; height: 50px;"></div>

  <!-- Badges -->
  <div class="badge" style="top: 60px; left: 30px;">
    <span class="badge-num">1</span>
    <span>本日の施術予約カード（居室番号・お名前・メニュー）</span>
  </div>

  <div class="badge yellow" style="top: 190px; left: 50px; font-size: 15px; padding: 7px 16px;">
    <span class="badge-num" style="width:24px; height:24px;">2</span>
    <span>⚠️【最重要】姿勢・認知症の注意点（施術前必読・スタッフからの申し送り）</span>
  </div>

  <div class="badge green" style="top: 370px; left: 40px;">
    <span class="badge-num">3</span>
    <span>施術完了報告ボタン（カルテ・家族へ即座に共有）</span>
  </div>
</body>
</html>
"""
render_annotated_image("barber_mode.html", "barber_mode_annotated.png", 1280, 800, html_barber)

print("🎉 All 5 annotated images generated successfully!")
