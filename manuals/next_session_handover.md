# 📋 次回再開用引き継ぎメモ (次回セッション用)

**更新日時**: 2026-09-30 17:30 (本日の作業終了時点)  
**次回メインテーマ**: **絵手紙のベース選択（新しく描く／前のをベースに）から下絵完成・画面表示の一連動作確認**

---

## 0. 本日完了した改修内容の要約

### ① 起動時の予定表示（予定カード）の自動起動を撤廃
* **課題**: 起動時にGeminiが「みまもりさん予定カードの表示をお願いします」と発言し、予定カードが勝手に開いていた。
* **対応**:
  * [`backend/gemini_live.py`](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/gemini_live.py): 起動時の予定表示指示を完全撤廃。挨拶は「太郎さん、こんにちは！何かお手伝いできることはありますか？」とシンプルに。
  * [`backend/main.py`](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/main.py): 接続時の予定カード初期状態を `visible: False`（非表示）に設定。
  * ※利用者が「予定は何？」「予定を見せて」と発言した時のみカードを表示。

### ② デジタル絵手紙の起動タイミング遅延（下絵準備完了まで遅らせる）
* **課題**: 「絵を描きたい」「聞こえますか?絵を描きたいです」と言った瞬間、正規表現が「聞こえますか?絵」をモチーフと誤認して先走ってカードを開いていた。
* **対応**:
  * [`backend/main.py`](file:///media/k3and4/For_AI_Data/Antigravity/TestApp/Nursing_facility/backend/main.py): 「絵」「絵手紙」「お絵描き」などの総称や、文脈の切れ端（「聞こえますか？」等）を除外するフィルターを強化。
  * 「絵を描きたい」と言った段階ではカードを開かず・下絵更新も走らせずに待機（フラグのみ保持）。
  * 下絵の作成中（生成中）に先行してカードを開く処理を撤廃。
  * モチーフが決まり、**実際に下絵（画像・メッセージ）の準備が完了した瞬間（`etegami_update`）に、初めて絵手紙カードを画面に起動・表示（`visible: True` + `force_open: True`）** するよう改修。

### ③ 絵手紙ベース選択（既存ベース／新規作成）の対話フロー確立 ＆ 音声アシスト
* **対話フロー確立**: 利用者が「絵を描きたい」と発言 ➔ Geminiが「以前作った絵手紙をベースにしますか？それとも新しく描きますか？」と確認。
* **即時モード確定＆アシスト**: 利用者が「新しく」「新しい絵」「前のでいい」「ベースにして」とお話しされた際、Whisper STTが直接検知して即座に制作モード（`generate_new` または `asset_base`）を確定。
  みまもりさんが音声TTS＋トーストで「🎨 みまもりさん：承知しました。新しい絵手紙ですね。どんな絵を描きましょうか？」と返答・アシスト。
* **タイムアウト緩和**: 発話終了（EOS）時のWhisper STTフォールバック有効期間を 1.5秒から 4.0秒へ緩和。

---

## 1. 次回再開時の手順

### Step 1: サーバー＆トンネルの起動
```bash
./start_all.sh
```
※FastAPIバックエンド（ポート8000）およびCloudflareトンネルが起動し、最新URLがGitHub Pagesへ自動反映されます。

### Step 2: 動作確認チェック項目
- [ ] **1. 起動時**:
  - 予定カードが画面に出ず、Geminiが「太郎さん、こんにちは！何かお手伝いできることはありますか？」と挨拶すること。
- [ ] **2. 「絵を描きたい」発言時**:
  - 絵手紙カードはまだ開かず、Geminiが「以前作った絵手紙をベースにしますか？それとも新しく描きますか？」と尋ねること。
- [ ] **3. 「新しく描きます」発言時**:
  - みまもりさんが「承知しました。新しい絵手紙ですね。どんな絵を描きましょうか？」と返答すること。
- [ ] **4. モチーフ指定（「白い犬を描いて」「小鳥を描いて」等）**:
  - みまもりさんが下絵を準備し、**完成した瞬間に絵手紙カードが目の前にパッと起動・表示されること**。

---

## 2. 動作確認用URL（固定）

* **居室端末（固定ゲートウェイURL）**:  
  [https://k3and4ai-sudo.github.io/Nursing_facility/user/?debug=true](https://k3and4ai-sudo.github.io/Nursing_facility/user/?debug=true)
* **ご家族見守りポータル**:  
  [https://k3and4ai-sudo.github.io/Nursing_facility/](https://k3and4ai-sudo.github.io/Nursing_facility/)
* **介護スタッフステーション**:  
  [https://k3and4ai-sudo.github.io/Nursing_facility/staff/](https://k3and4ai-sudo.github.io/Nursing_facility/staff/)
