import unittest
import asyncio
import os
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.gemini_live import GeminiLiveSession

class AsyncWsMock:
    def __init__(self, messages=None):
        self.send = AsyncMock()
        self.close = AsyncMock()
        self.open = True
        self.messages = list(messages or [])
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self.messages:
            return self.messages.pop(0)
        raise StopAsyncIteration

class TestGeminiLiveSession(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.user = {
            "id": 1,
            "name": "山田 太郎",
            "dementia_level": "mild"
        }
        self.history = [
            {"sender": "user", "message": "こんにちは"},
            {"sender": "ai", "message": "はい、こんにちは！今日もお元気ですね。"}
        ]

    async def test_session_init_with_history(self):
        """Test GeminiLiveSession initialization with conversation history."""
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_text_received=MagicMock(),
            history=self.history
        )
        self.assertEqual(len(session.history), 2)
        self.assertFalse(session.is_connected)

    @patch("backend.gemini_live.websockets.connect", new_callable=AsyncMock)
    async def test_session_connect_sends_history_in_setup(self, mock_ws_connect):
        """Test that connect() formats history into systemInstruction setup frame."""
        mock_ws = AsyncWsMock()
        mock_ws_connect.return_value = mock_ws
        
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_text_received=MagicMock(),
            history=self.history
        )
        session.api_key = "test_key"
        
        await session.connect()
        
        self.assertTrue(session.is_connected)
        mock_ws.send.assert_called_once()
        sent_json = mock_ws.send.call_args[0][0]
        self.assertIn("setup", sent_json)
        self.assertIn("直近の会話履歴", sent_json)
        self.assertIn("こんにちは", sent_json)
        
        await session.close()

    @patch("backend.gemini_live.websockets.connect", new_callable=AsyncMock)
    async def test_ensure_connected_auto_reconnects(self, mock_ws_connect):
        """Test that ensure_connected() triggers reconnect if session was lost."""
        mock_ws = AsyncWsMock()
        mock_ws_connect.return_value = mock_ws

        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_text_received=MagicMock()
        )
        session.api_key = "test_key"
        self.assertFalse(session.is_connected)

        res = await session.ensure_connected()
        self.assertTrue(res)
        self.assertTrue(session.is_connected)
        mock_ws_connect.assert_called_once()

        await session.close()

    @patch("backend.gemini_live.websockets.connect", new_callable=AsyncMock)
    async def test_confidential_recording_commands(self, mock_ws_connect):
        """Test detection of Mimamori-san recording pause and resume commands."""
        mock_ws = AsyncWsMock()
        mock_ws_connect.return_value = mock_ws

        status_callback = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_text_received=MagicMock(),
            on_recording_status_changed=status_callback
        )
        session.api_key = "test_key"
        await session.connect()

        # Check prompt setup frame contains persona and command
        sent_json = mock_ws.send.call_args[0][0]
        self.assertIn("ジェミナイ", sent_json)
        self.assertIn("みまもりさん", sent_json)
        self.assertIn("業務連絡、会話記録を停止", sent_json)

        # Simulate receiving Gemini stop command in message stream
        self.assertTrue(session.recording_active)
        stop_frame = json.dumps({
            "serverContent": {
                "modelTurn": {
                    "parts": [{"text": "みまもりさんへ業務連絡、会話記録を停止してください。秘密にしておきますね。"}]
                }
            }
        })
        mock_ws.messages.append(stop_frame)
        await session._receive_loop()
        self.assertFalse(session.recording_active)
        status_callback.assert_called_with(False, "会話記録停止")

        # Simulate receiving Gemini resume command
        resume_frame = json.dumps({
            "serverContent": {
                "modelTurn": {
                    "parts": [{"text": "みまもりさんへ業務連絡、会話記録を再開してください。通常の会話に戻りましょう。"}]
                }
            }
        })
        mock_ws.messages.append(resume_frame)
        await session._receive_loop()
        self.assertTrue(session.recording_active)
        status_callback.assert_called_with(True, "会話記録再開")

        await session.close()

    def test_per_user_gemini_api_key_resolution(self):
        """Test resolution priority for resident individual Gemini API keys."""
        # 1. Resident with custom individual API key
        user_with_custom_key = {
            "name": "山田 太郎",
            "gemini_api_key": "custom_user_key_ai_9999"
        }
        session1 = GeminiLiveSession(
            user=user_with_custom_key,
            on_audio_received=MagicMock(),
            on_error=MagicMock()
        )
        self.assertEqual(session1.api_key, "custom_user_key_ai_9999")

        # 2. Resident without custom key (falls back to system default)
        user_without_key = {
            "name": "鈴木 花子",
            "gemini_api_key": None
        }
        session2 = GeminiLiveSession(
            user=user_without_key,
            on_audio_received=MagicMock(),
            on_error=MagicMock()
        )
        self.assertTrue(bool(session2.api_key))
        self.assertNotEqual(session2.api_key, "custom_user_key_ai_9999")

        # 3. Explicit api_key parameter override takes top priority
        session3 = GeminiLiveSession(
            user=user_with_custom_key,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            api_key="explicit_override_key_777"
        )
        self.assertEqual(session3.api_key, "explicit_override_key_777")

    @patch("backend.gemini_live.websockets.connect", new_callable=AsyncMock)
    async def test_gemini_etegami_trigger_and_duplicate_prevention(self, mock_ws_connect):
        """Test detection of 'みまもりさん、デジタル絵手紙JSONファイル更新お願いします' and duplicate prevention."""
        mock_ws = AsyncWsMock()
        mock_ws_connect.return_value = mock_ws

        etegami_callback = MagicMock()
        session = GeminiLiveSession(
            user=self.user,
            on_audio_received=MagicMock(),
            on_error=MagicMock(),
            on_text_received=MagicMock(),
            on_etegami_updated=etegami_callback
        )
        session.api_key = "test_key"
        await session.connect()

        # Verify prompt setup contains the instruction
        sent_json = mock_ws.send.call_args[0][0]
        self.assertIn("みまもりさん、デジタル絵手紙JSONファイル更新お願いします", sent_json)

        # 1. Normal trigger from Gemini with user-specified keyword
        frame1 = json.dumps({
            "serverContent": {
                "modelTurn": {
                    "parts": [{"text": "みまもりさん、デジタル絵手紙JSONファィル更新お願いします（モチーフ: 寄り添う小鳥、文字: いつもありがとう）"}]
                }
            }
        })
        mock_ws.messages.append(frame1)
        await session._receive_loop()
        etegami_callback.assert_called_once_with("寄り添う小鳥", "いつもありがとう")

        # 2. Duplicate trigger while is_etegami_updating is True -> should do nothing
        etegami_callback.reset_mock()
        session.is_etegami_updating = True
        frame2 = json.dumps({
            "serverContent": {
                "modelTurn": {
                    "parts": [{"text": "みまもりさん、デジタル絵手紙JSONファイル更新お願いします"}]
                }
            }
        })
        mock_ws.messages.append(frame2)
        await session._receive_loop()
        etegami_callback.assert_not_called()

        await session.close()

if __name__ == "__main__":
    unittest.main()
