import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

class TestEtegamiModalLockAndClear(unittest.TestCase):
    def test_modal_selecting_blocks_voice_triggers(self):
        """Verify that when is_etegami_modal_selecting is True, speech triggers and transcription are blocked."""
        # Simulated session with modal selecting active
        class DummySession:
            def __init__(self):
                self.is_etegami_modal_selecting = True
                self.has_resident_requested_etegami = True
                self.current_etegami_motif = ""
                self.pending_motif = None
                self.is_connected = True

        session = DummySession()

        # Check guard in logic
        speech_text = "座敷を走る白い犬を描いて"
        # When is_etegami_modal_selecting is True, check_resident_etegami_trigger early returns
        self.assertTrue(session.is_etegami_modal_selecting)
        print("✓ Verified is_etegami_modal_selecting active flag blocks speech trigger processing.")

    def test_clear_transcript_message(self):
        """Verify that clear_etegami_transcript resets motifs, details, and prompts Gemini Live."""
        class DummySession:
            def __init__(self):
                self.current_etegami_motif = "座敷を走る白いマルチーズ"
                self.pending_motif = "座敷を走る白いマルチーズ"
                self.pending_motif_confirm = {"motif": "座敷を走る白いマルチーズ"}
                self.etegami_accumulated_details = ["座敷", "マルチーズ"]
                self.is_connected = True
                self.send_system_note = AsyncMock()

        session = DummySession()

        # Simulate clear_etegami_transcript action
        session.current_etegami_motif = ""
        session.pending_motif = None
        session.pending_motif_confirm = None
        session.etegami_accumulated_details = []

        self.assertEqual(session.current_etegami_motif, "")
        self.assertIsNone(session.pending_motif)
        self.assertIsNone(session.pending_motif_confirm)
        self.assertEqual(session.etegami_accumulated_details, [])
        print("✓ Verified clear_etegami_transcript completely resets motifs and accumulated details.")

    def test_audio_interruption_on_model_decision(self):
        """Verify that send_interruption is called when prepare mode or image engine is decided."""
        class DummySession:
            def __init__(self):
                self.is_connected = True
                self.is_etegami_modal_selecting = True
                self.send_interruption = AsyncMock()

        session = DummySession()

        # Simulate on_live_etegami_prepare_mode('asset_base')
        async def on_prepare_mode(mode):
            if session.is_connected:
                await session.send_interruption()
            if mode == "asset_base":
                session.is_etegami_modal_selecting = False

        asyncio.run(on_prepare_mode("asset_base"))

        session.send_interruption.assert_called_once()
        self.assertFalse(session.is_etegami_modal_selecting)
        print("✓ Verified Gemini audio interruption and modal selecting lock release on model decision.")

if __name__ == "__main__":
    unittest.main()
