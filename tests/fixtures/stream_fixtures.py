"""
Realistic streaming response fixtures matching Google's raw wire protocol.
"""
import json

def make_stream_chunk(
    content_text: str = None,
    conv_id: str = None,
    continuation_token: str = None,
    image_url: str = None,
) -> str:
    """
    Constructs a JSON-wrapped stream line matching Gemini's StreamGenerate chunk format:
    line = [ [ null, null, json_string_payload ] ]
    """
    inner_payload = [None] * 5

    if conv_id:
        conv_block = [conv_id]
        if continuation_token:
            conv_block = [conv_id, None, None, None, None, None, None, continuation_token]
        inner_payload[1] = conv_block

    parts = []
    if content_text:
        parts.append(content_text)
    if image_url:
        parts.append(f"Image link: {image_url}")

    if parts:
        inner_payload[4] = [
            [
                None,
                parts,
            ]
        ]

    chunk_json = [[None, None, json.dumps(inner_payload)]]
    return json.dumps(chunk_json)

# Sample realistic raw lines
SAMPLE_TEXT_LINE = make_stream_chunk(
    content_text="這是測試回答第一部分",
    conv_id="c_11d858511efb9729",
    continuation_token="AwAAAAAAAAAQANM7mBjXKZS5cPttExo",
)
SAMPLE_IMAGE_LINE = make_stream_chunk(
    image_url="https://lh3.googleusercontent.com/gg-dl/ABcDeFgHiJkLmNoPqRsTuVwXyZ=s0-d"
)
