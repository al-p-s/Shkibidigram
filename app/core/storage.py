from minio import Minio
from minio.error import S3Error

from app.config import settings

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=False,
)


def init_buckets() -> None:
    for bucket in [settings.minio_bucket_media, settings.minio_bucket_avatars]:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)


async def upload_file(
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    import io

    minio_client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"http://{settings.minio_endpoint}/{bucket}/{object_name}"


async def delete_file(bucket: str, object_name: str) -> None:
    try:
        minio_client.remove_object(bucket, object_name)
    except S3Error:
        pass
