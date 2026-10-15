import unittest
from gemini_flow.infrastructure.clients.http_client import CaseInsensitiveDict


class TestCaseInsensitiveDict(unittest.TestCase):
    def test_case_insensitive_lookup(self):
        d = CaseInsensitiveDict({"X-Goog-Upload-Url": "https://upload.example.com", "Content-Type": "text/plain"})
        self.assertEqual(d["x-goog-upload-url"], "https://upload.example.com")
        self.assertEqual(d["X-GOOG-UPLOAD-URL"], "https://upload.example.com")
        self.assertEqual(d["X-Goog-Upload-Url"], "https://upload.example.com")
        self.assertEqual(d.get("x-goog-upload-url"), "https://upload.example.com")
        self.assertEqual(d.get("X-Goog-Upload-Url"), "https://upload.example.com")

    def test_containment(self):
        d = CaseInsensitiveDict({"x-goog-upload-status": "active"})
        self.assertIn("X-Goog-Upload-Status", d)
        self.assertIn("x-goog-upload-status", d)
        self.assertNotIn("non-existent-header", d)

    def test_preserves_original_casing_on_iteration(self):
        d = CaseInsensitiveDict({"X-Custom-Header": "val1", "accept-encoding": "gzip"})
        keys = list(d)
        self.assertIn("X-Custom-Header", keys)
        self.assertIn("accept-encoding", keys)

    def test_get_with_default(self):
        d = CaseInsensitiveDict({"a": "1"})
        self.assertEqual(d.get("b", "default_val"), "default_val")
        self.assertIsNone(d.get("b"))

    def test_equality_with_dict(self):
        d = CaseInsensitiveDict({"Header-A": "1", "header-b": "2"})
        self.assertEqual(d, {"header-a": "1", "HEADER-B": "2"})


if __name__ == "__main__":
    unittest.main()
