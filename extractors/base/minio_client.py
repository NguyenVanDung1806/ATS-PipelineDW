"""MinIO client factory — use this everywhere, never instantiate boto3 directly."""
import boto3, os


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    )


def ensure_bucket_exists(bucket: str | None = None) -> None:
    """Call once during setup. MinIO doesn't auto-create buckets."""
    bucket = bucket or os.environ.get("MINIO_BUCKET", "datalake")
    client = get_minio_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
        print(f"Created bucket: {bucket}")
