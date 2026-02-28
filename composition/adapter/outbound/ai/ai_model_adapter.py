import httpx

from composition.application.ports.outbound.ai_model_port import (
    AiCompositionRequest,
    AiCompositionResult,
    AiModelPort,
)


class AiModelAdapter(AiModelPort):
    def __init__(self, api_url: str, api_key: str):
        self._api_url = api_url
        self._api_key = api_key

    def compose(self, request: AiCompositionRequest) -> AiCompositionResult:
        response = httpx.post(
            self._api_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "base_url": request.base_url,
                "overlay_url": request.overlay_url,
            },
        )
        response.raise_for_status()
        data = response.json()
        return AiCompositionResult(result_url=data["result_url"])
