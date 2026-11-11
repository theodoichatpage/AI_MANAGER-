import sys
import tempfile
import unittest
from pathlib import Path

from studio_monitor import StudioMonitor


@unittest.skipUnless(sys.platform == 'win32', 'the pairing code is stored only with Windows DPAPI')
class StudioPairingTests(unittest.TestCase):
    def test_pairing_survives_a_restart_encrypted_and_disconnect_forgets_it(self):
        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / 'studio_pairing.bin'
            code = 'e6ae3139a690474ca5db6654cdc5f9b5'
            first = StudioMonitor(reader=lambda c: {}, store=store)
            first.configure(code)
            self.assertTrue(store.is_file())
            self.assertNotIn(code.encode(), store.read_bytes())
            restarted = StudioMonitor(reader=lambda c: {}, store=store)
            self.assertEqual(restarted.code, code)
            self.assertTrue(restarted.snapshot()['configured'])
            restarted.disconnect()
            self.assertFalse(store.exists())
            self.assertFalse(StudioMonitor(reader=lambda c: {}, store=store).snapshot()['configured'])

    def test_a_damaged_store_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / 'studio_pairing.bin'
            store.write_bytes(b'not a dpapi blob')
            self.assertFalse(StudioMonitor(reader=lambda c: {}, store=store).snapshot()['configured'])


if __name__ == '__main__':
    unittest.main()
