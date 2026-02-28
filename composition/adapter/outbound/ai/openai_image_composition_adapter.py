from composition.application.ports.outbound.image_composition_port import (
    ImageCompositionPort,
    ImageCompositionRequest,
    ImageCompositionResult,
)


class OpenAiImageCompositionAdapter(ImageCompositionPort):
    def __init__(self, api_url: str, api_key: str):
        self._api_url = api_url
        self._api_key = api_key

    def compose(self, request: ImageCompositionRequest) -> ImageCompositionResult:
        # TODO: OpenAI 이미지 합성 API 연동 구현
        raise NotImplementedError
