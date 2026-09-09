"""
backend/test_consultation_json.py
Tests consultation image prompt extraction with Ollama LLM and privacy preservation.
"""

import os
import sys
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import multimedia, database as db

def test_consultation_extraction():
    print("=== Test 1: Money / Pension Concern with Specific Amount ===")
    mock_history_money = [
        {"sender": "user", "message": "あのね、年金の通知が届いたんやけど、月12万円でこれからやっていけるか心配でね。"},
        {"sender": "gemini", "message": "大切なお金のことですから、これからの生活のご不安なお気持ち、よく分かりますよ。"},
        {"sender": "user", "message": "貯金も50万円くらいしかあらへんし、子どもたちに迷惑かけへんかと思って…"},
        {"sender": "gemini", "message": "ご家族のことを本当に大切に想っていらっしゃるのですね。でも一人で抱え込まず、ゆっくりお茶でも飲みながらお話ししてくださいね。"}
    ]

    payload_money = multimedia.extract_image_prompt_from_conversation(
        user_id=1,
        terminal_id="term-01",
        chat_history=mock_history_money
    )

    print("Result Payload Money:")
    print(json.dumps(payload_money, indent=2, ensure_ascii=False))

    # Verify no raw amounts leaked into positive prompt or headline
    serialized = json.dumps(payload_money, ensure_ascii=False)
    assert "12万" not in serialized, "Specific amount leaked into payload!"
    assert "50万" not in serialized, "Specific amount leaked into payload!"
    print(">>> PASS: Specific amounts protected.")

    print("\n=== Test 2: Daily Complaint / Physical Pain / Dementia Wandering Anxiety ===")
    mock_history_complaint = [
        {"sender": "user", "message": "最近腰が痛くてねえ。夜も目が覚めるし、誰も話を聞いてくれへんのよ。"},
        {"sender": "gemini", "message": "腰がお辛いと夜も眠れずしんどいですね。私がいつでもお聞きしますからね。"},
        {"sender": "user", "message": "昔は元気に畑仕事もできたのに、情けなくなってくるわ。"},
        {"sender": "gemini", "message": "これまでたくさん頑張ってこられたお身体ですものね。今日はお茶でも飲んでゆっくりお身体を休めてくださいね。"}
    ]

    payload_complaint = multimedia.extract_image_prompt_from_conversation(
        user_id=1,
        terminal_id="term-01",
        chat_history=mock_history_complaint
    )

    print("Result Payload Complaint:")
    print(json.dumps(payload_complaint, indent=2, ensure_ascii=False))
    assert payload_complaint.get("topic_category") == "consultation"
    print(">>> PASS: Correctly classified as consultation.")

if __name__ == "__main__":
    test_consultation_extraction()
