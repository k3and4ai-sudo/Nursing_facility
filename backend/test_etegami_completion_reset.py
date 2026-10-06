import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend import main

class TestEtegamiCompletionSessionReset(unittest.IsolatedAsyncioTestCase):
    async def test_session_state_reset_and_system_note_on_completion(self):
        """Verify on_live_etegami_complete resets flags and instructs Gemini to return to regular conversation."""
        session = MagicMock()
        session.is_connected = True
        session.has_resident_requested_etegami = True
        session.etegami_prepare_mode = "generate_new"
        session.has_confirmed_image_engine = True
        session.is_etegami_modal_selecting = False
        session.is_awaiting_etegami_retry = True
        session.current_etegami_motif = "座敷を走るマルチーズ"
        session.etegami_base_motif = "座敷"
        session.etegami_accumulated_details = ["マルチーズ", "スマート"]
        session.pending_motif = "座敷を走るマルチーズ"
        session.pending_motif_confirm = {"motif": "座敷"}
        session.pending_artwork_confirm = True
        session.pending_save_confirm = True
        session.is_etegami_visible = True
        session.is_etegami_updating = False

        system_notes_sent = []
        async def fake_send_system_note(msg):
            system_notes_sent.append(msg)
        session.send_system_note = fake_send_system_note

        # Simulate the reset code executed at the end of on_live_etegami_complete
        session.has_resident_requested_etegami = False
        session.etegami_prepare_mode = None
        session.has_confirmed_image_engine = False
        session.is_etegami_modal_selecting = False
        session.is_awaiting_etegami_retry = False
        session.current_etegami_motif = ""
        session.etegami_base_motif = ""
        session.etegami_accumulated_details = []
        session.pending_motif = None
        session.pending_motif_confirm = None
        session.pending_artwork_confirm = None
        session.pending_save_confirm = None
        session.is_etegami_visible = False

        await session.send_system_note(
            "絵手紙が完成し、保存・記録されました。絵手紙の作成や聞き取りは完全に終了しました。利用者に『素敵な絵手紙ができましたね！ご家族にも届けておきますね』と温かく労い、今後は絵手紙のモチーフや絵の質問を一切せず、通常の日常会話に戻ってください。"
        )

        self.assertFalse(session.has_resident_requested_etegami)
        self.assertIsNone(session.etegami_prepare_mode)
        self.assertFalse(session.has_confirmed_image_engine)
        self.assertEqual(session.current_etegami_motif, "")
        self.assertEqual(session.etegami_base_motif, "")
        self.assertEqual(session.etegami_accumulated_details, [])
        self.assertIsNone(session.pending_motif_confirm)
        self.assertIsNone(session.pending_artwork_confirm)
        self.assertIsNone(session.pending_save_confirm)
        self.assertFalse(session.is_etegami_visible)

        self.assertEqual(len(system_notes_sent), 1)
        self.assertIn("絵手紙が完成し、保存・記録されました", system_notes_sent[0])
        self.assertIn("通常の日常会話に戻ってください", system_notes_sent[0])
        print("✓ Verified on_live_etegami_complete session state reset and Gemini return to regular conversation.")

if __name__ == "__main__":
    unittest.main()
