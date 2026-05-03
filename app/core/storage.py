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
        try:
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
        except S3Error as e:
            if e.code != "BucketAlreadyOwnedByYou":
                raise


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


def get_file_stream(bucket: str, object_name: str):
    response = minio_client.get_object(bucket, object_name)
    content_type = response.headers.get("Content-Type", "application/octet-stream")

    def chunk_generator():
        try:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return chunk_generator(), content_type


async def delete_file(bucket: str, object_name: str) -> None:
    try:
        minio_client.remove_object(bucket, object_name)
    except S3Error:
        pass
