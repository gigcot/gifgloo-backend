from composition.application.ports.outbound.asset_fetch_port import AssetFetchPort, AssetInfo


class AssetFetchAdapter(AssetFetchPort):
    """
    Asset 도메인의 Application Service를 호출해서 에셋 정보를 가져온다.
    Asset 도메인이 구현되면 asset_service 를 주입받아 사용한다.
    """

    def __init__(self, asset_service):
        self._asset_service = asset_service

    def fetch(self, asset_id: str) -> AssetInfo:
        return self._asset_service.get_asset_info(asset_id)
