from asset.application.ports.outbound.s3.upload import UploadToS3Command, UploadToS3Port, UploadToS3Result

class UploadToS3Adapter(UploadToS3Port):
    def __init__(self, client: ...):
        ...

    def execute(self, command: UploadToS3Command) -> UploadToS3Result:
        # TODO: boto3연결?
        raise NotImplementedError

