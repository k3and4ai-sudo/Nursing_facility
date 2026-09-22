# 📚 CareLink（ケアリンク）マニュアル・総合インデックス
### 〜 施設見守りシステム 4大ポータル 操作手引き＆検証手順書 〜

本フォルダ（`manuals/`）は、介護施設向け統合AI見守りシステム「CareLink（ケアリンク）」の各種操作マニュアルおよび検証手順書をまとめた総合インデックスです。

ご利用対象者（入居者様・ご家族様・施設スタッフ・理美容師様・外部評価者様）に合わせて、最適なマニュアルをお選びいただけます。

---

## 🚀 クイックナビゲーション（目的別マニュアル）

| ポータル / 対象 | マニュアル名 | 主な内容・特徴 | 形式 |
| :--- | :--- | :--- | :---: |
| 🏠 **入居者様**<br>（居室タブレット） | **[01. 居室端末 かんたん使い方ガイド](01_居室端末_かんたん使い方ガイド.md)** | ・みどりのおはなしボタン（1回押すだけ）<br>・Gemini Live音声対話と昔の思い出アルバム<br>・緊急時のたすけてボタン（SOS自動通報） | Markdown |
| 🏥 **施設スタッフ**<br>（PC / iPad） | **[02. 介護スタッフステーション 業務操作マニュアル](02_介護スタッフステーション_業務操作マニュアル.md)** | ・全居室見守りマトリクスの監視<br>・緊急SOS・転倒アラートの初動対応フロー<br>・Google Fit生体データ連携・AI日報自動生成 | Markdown |
| 👨‍👩‍👧 **ご家族様**<br>（スマホ / PC） | **[03. ご家族見守りポータル 利用ガイド](03_ご家族見守りポータル_利用ガイド.md)** | ・日々の健康状態（体温・血圧・ご機嫌）確認<br>・昭和レトロ水彩画「デジタル絵手紙」と四季着せ替え<br>・ハガキ印刷 ＆ 居室直通インターホン通話 | Markdown |
| 💈 **訪問理美容師**<br>（スマホ推奨） | **[04. 訪問理容・美容師ポータル 利用手引き](04_訪問理容・美容師ポータル_利用手引き.md)** | ・本日の施術予約一覧（部屋番号・メニュー）<br>・⚠️【最重要】姿勢・認知症の注意点チェック<br>・青色ボタンで施術完了報告（カルテ・家族へ即共有） | Markdown |
| 🌐 **管理者・全関係者**<br>（接続先一覧） | **[05. 各ポータルサイト接続URLガイド](05_各ポータルサイト接続URLガイド.md)** | ・全ポータルの施設内LAN ＆ 外部接続URL一覧<br>・デモ用ログインID / パスワード一覧<br>・ホーム画面追加（アプリ化手順）＆トラブル対応 | Markdown |
| 🧪 **外部評価・テスター**<br>（検証手順書） | **[06. 第三者検証マニュアル 外部接続・操作テスト手順書](06_第三者検証マニュアル_外部接続・操作テスト手順書.md)** | ・ケアリンクの概要・4大特徴の解説<br>・各画面の高解像度QRコード一覧<br>・第三者検証用チェックシート＆評価項目 | Markdown<br>＋<br>**[📄 PDF版](CareLink_第三者検証マニュアル.pdf)** |
| 📐 **開発者・管理者**<br>（全体アーキテクチャ） | **[CareLink システム全体仕様書 (Obsidian対応)](CareLink_System_Specification_Obsidian.md)** | ・Gemini Live × みまもりくん(Qwen 2.5) ハイブリッドAI構成<br>・施設IoT、ミリ波レーダー、Google Fit、WebSocket仕様<br>・Obsidianナレッジベース＆Mermaid設計図を完全完備 | Markdown<br>(Obsidian) |
| 🛠️ **開発者・運用者**<br>（端末管理・復旧） | **[08. 居室端末 端末登録と利用者紐付け開発者マニュアル](08_居室端末_端末登録と利用者紐付けトラブルシューティング開発者マニュアル.md)** | ・「端末の登録が必要です」表示時の復旧手順<br>・スタッフステーションからの利用者紐付けフロー<br>・URLパラメータによる即時復旧とSQLiteデータ仕様 | Markdown<br>(Obsidian) |

---

## 📄 配布・印刷用 PDFマニュアル
外部テスター様やスタッフ様への配布・印刷に最適な、A4カラー2枚構成のPDFマニュアルです。ログインなしで直接ダウンロードいただけます。

👉 **[CareLink_第三者検証マニュアル.pdf をダウンロード（直接保存）](https://github.com/k3and4ai-sudo/Nursing_facility/raw/main/manuals/CareLink_%E7%AC%AC%E4%B8%89%E8%80%85%E6%A4%9C%E8%A8%BC%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB.pdf)**

---

## 🌐 実際のポータルサイトへの接続リンク（Web実機）
各ポータルサイトは外部インターネット（GitHub Pages / トンネル）経由で稼働しており、お手持ちのスマートフォンやPCから直接お試しいただけます。

- **🏥 介護スタッフステーション**: [https://k3and4ai-sudo.github.io/Nursing_facility/staff/](https://k3and4ai-sudo.github.io/Nursing_facility/staff/)  
  *(ID: `staff01` / PASS: `staff123`)*
- **💈 訪問理容・美容師ポータル**: [https://k3and4ai-sudo.github.io/Nursing_facility/barber/](https://k3and4ai-sudo.github.io/Nursing_facility/barber/)  
  *(ワンタップ自動ログイン対応)*
- **👨‍👩‍👧 ご家族見守りポータル**: [https://k3and4ai-sudo.github.io/Nursing_facility/](https://k3and4ai-sudo.github.io/Nursing_facility/)  
  *(ID: `family01` / PASS: `family123`)*
- **🏠 居室端末（かんたん対話）**: [https://k3and4ai-sudo.github.io/Nursing_facility/user/](https://k3and4ai-sudo.github.io/Nursing_facility/user/)  
  *(自動接続: 101号室 山田様)*

---

## 🖼️ マニュアル解説用 注釈画像（アノテーション画像）
すべてのマニュアルには、画面上の実際のボタンや枠線の色と完全に連動した高解像度のアノテーション画像が埋め込まれています。

- **居室端末（かんたん画面）**: [resident_room_annotated_simple.png](../assets/manual_images/resident_room_annotated_simple.png)
- **居室端末（くわしい画面）**: [resident_room_annotated_detailed.png](../assets/manual_images/resident_room_annotated_detailed.png)
- **スタッフステーション**: [staff_dashboard_annotated.png](../assets/manual_images/staff_dashboard_annotated.png)
- **ご家族ポータル（スマホ版）**: [family_portal_mobile_annotated.png](../assets/manual_images/family_portal_mobile_annotated.png)
- **ご家族ポータル（PC上部画面）**: [family_portal_pc_top_annotated.png](../assets/manual_images/family_portal_pc_top_annotated.png)
- **ご家族ポータル（PC下部画面）**: [family_portal_pc_bottom_annotated.png](../assets/manual_images/family_portal_pc_bottom_annotated.png)
- **訪問理美容師ポータル**: [barber_mode_annotated.png](../assets/manual_images/barber_mode_annotated.png)
