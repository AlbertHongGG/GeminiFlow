import unittest
from gemini_flow.domain.entities import ImagePayload
from gemini_flow.domain.exceptions import NetworkError
from gemini_flow.infrastructure.clients.gemini_uploader import GeminiImageUploader
from tests.fakes import FakeHttpClient
from tests.fakes.fake_http_client import FakeHttpResponse


class MockHttpClientForUpload(FakeHttpClient):
    def __init__(self, step1_response: FakeHttpResponse, step2_response: FakeHttpResponse):
        super().__init__()
        self.step1_response = step1_response
        self.step2_response = step2_response
        self.post_form_calls = []

    async def post_form(self, url, data=None, headers=None):
        self.post_form_calls.append((url, data, headers))
        if len(self.post_form_calls) == 1:
            return self.step1_response
        return self.step2_response


class TestGeminiImageUploader(unittest.IsolatedAsyncioTestCase):
    async def test_upload_success_with_http2_lowercase_headers(self):
        step1_resp = FakeHttpResponse(
            status_code=200,
            headers={"x-goog-upload-url": "https://push.clients6.google.com/upload/?upload_id=test_123"},
        )
        step2_resp = FakeHttpResponse(
            status_code=200,
            content=b"/contrib_service/ttl_1d/uploaded_image_hash_789\n",
        )
        http_client = MockHttpClientForUpload(step1_resp, step2_resp)
        uploader = GeminiImageUploader(http_client)

        images = [ImagePayload(data=b"\xff\xd8\xff\xe0mockjpeg", filename="test.jpg")]
        uploads = await uploader.upload_images(images)

        self.assertEqual(len(uploads), 1)
        ref, name = uploads[0]
        self.assertEqual(ref, "/contrib_service/ttl_1d/uploaded_image_hash_789")
        self.assertEqual(name, "test.jpg")

        # Verify step 1 headers included content length
        self.assertEqual(len(http_client.post_form_calls), 2)
        step1_url, step1_data, step1_headers = http_client.post_form_calls[0]
        self.assertEqual(step1_headers["x-goog-upload-command"], "start")
        self.assertEqual(step1_headers["x-goog-upload-header-content-length"], str(len(b"\xff\xd8\xff\xe0mockjpeg")))
        self.assertEqual(step1_data, "File name: test.jpg")

        # Verify step 2 posted to the session url
        step2_url, step2_data, step2_headers = http_client.post_form_calls[1]
        self.assertEqual(step2_url, "https://push.clients6.google.com/upload/?upload_id=test_123")
        self.assertEqual(step2_headers["x-goog-upload-command"], "upload, finalize")
        self.assertEqual(step2_data, b"\xff\xd8\xff\xe0mockjpeg")

    async def test_upload_success_with_titlecase_headers(self):
        step1_resp = FakeHttpResponse(
            status_code=200,
            headers={"X-Goog-Upload-Url": "https://push.clients6.google.com/upload/?upload_id=title_case_id"},
        )
        step2_resp = FakeHttpResponse(
            status_code=200,
            content=b"/contrib_service/ttl_1d/title_case_ref",
        )
        http_client = MockHttpClientForUpload(step1_resp, step2_resp)
        uploader = GeminiImageUploader(http_client)

        images = [ImagePayload(data=b"bytes", filename="pic.png")]
        uploads = await uploader.upload_images(images)

        self.assertEqual(uploads[0][0], "/contrib_service/ttl_1d/title_case_ref")

    async def test_upload_step1_non_200_raises_network_error(self):
        step1_resp = FakeHttpResponse(status_code=403, content=b"Forbidden")
        step2_resp = FakeHttpResponse(status_code=200)
        http_client = MockHttpClientForUpload(step1_resp, step2_resp)
        uploader = GeminiImageUploader(http_client)

        with self.assertRaises(NetworkError) as cm:
            await uploader.upload_images([ImagePayload(data=b"data", filename="1.jpg")])
        self.assertIn("403", str(cm.exception))

    async def test_upload_step1_missing_upload_url_raises_network_error(self):
        step1_resp = FakeHttpResponse(status_code=200, headers={"server": "uploadserver"})
        step2_resp = FakeHttpResponse(status_code=200)
        http_client = MockHttpClientForUpload(step1_resp, step2_resp)
        uploader = GeminiImageUploader(http_client)

        with self.assertRaises(NetworkError) as cm:
            await uploader.upload_images([ImagePayload(data=b"data", filename="1.jpg")])
        self.assertIn("Missing 'x-goog-upload-url'", str(cm.exception))

    async def test_upload_step2_failure_raises_network_error(self):
        step1_resp = FakeHttpResponse(
            status_code=200,
            headers={"x-goog-upload-url": "https://upload.url"},
        )
        step2_resp = FakeHttpResponse(status_code=500, content=b"Internal Server Error")
        http_client = MockHttpClientForUpload(step1_resp, step2_resp)
        uploader = GeminiImageUploader(http_client)

        with self.assertRaises(NetworkError) as cm:
            await uploader.upload_images([ImagePayload(data=b"data", filename="1.jpg")])
        self.assertIn("500", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
