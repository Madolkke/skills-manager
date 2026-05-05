import tempfile
import unittest
from pathlib import Path

from skillhub_demo.artifact_store import FileArtifactStore


class ArtifactStoreTest(unittest.TestCase):
    def test_file_artifact_store_round_trips_text_by_locator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileArtifactStore(Path(tmpdir))
            locator = store.write_text("skill-bundles", "abc123", '{"ok": true}')

            self.assertEqual(locator, "file:skill-bundles/abc123.json")
            self.assertEqual(store.read_text(locator), '{"ok": true}')

    def test_file_artifact_store_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileArtifactStore(Path(tmpdir))

            with self.assertRaisesRegex(ValueError, "Invalid artifact locator"):
                store.read_text("file:../secret.json")


if __name__ == "__main__":
    unittest.main()
