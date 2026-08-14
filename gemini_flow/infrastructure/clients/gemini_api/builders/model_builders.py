import json
from typing import List, Dict
from .base_builder import BasePayloadBuilder

class StandardModelBuilder(BasePayloadBuilder):
    def _build_inner_request(self, c_id: str, r_id: str, rc_id: str, p79: int, p80: int) -> List:
        image_list = [
            [[upload_ref, 1], image_name] for upload_ref, image_name in self.uploads
        ]
        return [
            [self.prompt, 0, None, image_list, None, None, 0],
            [self.request.language],
            [c_id, r_id, rc_id, None, None, None, None, None, None, ""],
            None,
            None,
            None,
            [1],
            0,
            [],
            [],
            1,
            0,
        ]

class ProModelBuilder(BasePayloadBuilder):
    def _build_inner_request(self, c_id: str, r_id: str, rc_id: str, p79: int, p80: int) -> List:
        image_list = [
            [[upload_ref, 1], image_name] for upload_ref, image_name in self.uploads
        ]
        
        arr = [None] * 97
        arr[0] = [self.prompt, 0, None, image_list, None, None, 0]
        arr[1] = [self.request.language]
        arr[2] = [c_id, r_id, rc_id, None, None, None, None, None, None, ""]
        arr[6] = [0]
        arr[7] = 1
        arr[10] = 1
        arr[11] = 0
        arr[17] = [[1]] if p80 == 2 else [[0]]
        arr[18] = 0
        arr[27] = 1
        arr[30] = [4]
        arr[41] = [1]
        arr[53] = 0
        arr[59] = self.req_uuid
        arr[61] = [1]
        arr[67] = 0
        arr[68] = 1
        arr[79] = p79
        arr[80] = p80
        arr[91] = 0
        arr[96] = 0
        return arr

    def _enrich_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers["x-goog-ext-525005358-jspb"] = json.dumps([self.req_uuid, 1], separators=(",", ":"))
        return headers

def get_builder_for_model(request, tokens, uploads, conversation_ids) -> BasePayloadBuilder:
    model_name = request.model.lower()
    if "pro" in model_name or "flash" in model_name:
        return ProModelBuilder(request, tokens, uploads, conversation_ids)
    return StandardModelBuilder(request, tokens, uploads, conversation_ids)
