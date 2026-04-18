import uuid

import boto3

from app.core.config import settings


s3_client = boto3.client("s3", region_name=settings.aws_region)


def presign_upload(filename: str, content_type: str) -> tuple[str, str]:
    object_key = f"reports/{uuid.uuid4()}-{filename}"
    upload_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": settings.s3_bucket, "Key": object_key, "ContentType": content_type},
        ExpiresIn=900,
    )
    return upload_url, object_key
