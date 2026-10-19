import unittest
import hashlib
from gemini_flow.infrastructure.auth.sapisid_signer import SAPISIDSigner

class TestSAPISIDSigner(unittest.TestCase):
    def test_compute_hash_deterministic(self):
        sapisid = "rce7m8PlBSHp71HL/A2_loUgK6ANHdlYsJ"
        ts = 1792435920
        origin = "https://gemini.google.com"
        
        expected_digest = hashlib.sha1(f"{ts} {sapisid} {origin}".encode()).hexdigest()
        self.assertEqual(expected_digest, "11a3f87ba3856e8ad3a734d455c3d01092a9fc08")
        
        header = SAPISIDSigner.compute_hash(sapisid, origin=origin, timestamp=ts)
        expected_header = (
            f"SAPISIDHASH 1792435920_{expected_digest} "
            f"SAPISID1PHASH 1792435920_{expected_digest} "
            f"SAPISID3PHASH 1792435920_{expected_digest}"
        )
        self.assertEqual(header, expected_header)

    def test_get_authorization_header_from_cookies(self):
        cookies = {
            "SAPISID": "test_sapisid_value",
            "SID": "some_sid",
        }
        ts = 1700000000
        header = SAPISIDSigner.get_authorization_header(cookies, timestamp=ts)
        self.assertIn("SAPISIDHASH 1700000000_", header)
        self.assertIn("SAPISID1PHASH 1700000000_", header)
        self.assertIn("SAPISID3PHASH 1700000000_", header)

    def test_missing_sapisid_raises(self):
        with self.assertRaises(ValueError):
            SAPISIDSigner.compute_hash("")
