#!/usr/bin/env python3
"""Initialize MinIO bucket and folders."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

FOLDERS = ["raw/facebook/ads/","raw/google/ads/","raw/tiktok/ads/",
           "raw/zalo/ads/","raw/crm/leads/","processed/"]

def init():
    from extractors.base.minio_client import get_minio_client
    bucket = os.environ.get("MINIO_BUCKET", "ats-datalake")
    client = get_minio_client()
    try:
        client.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' exists")
    except:
        client.create_bucket(Bucket=bucket)
        print(f"Created bucket: {bucket}")
    for f in FOLDERS:
        client.put_object(Bucket=bucket, Key=f+".keep", Body=b"")
        print(f"Created: {f}")

if __name__ == "__main__":
    init()
