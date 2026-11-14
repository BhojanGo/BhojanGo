"""Move a file through the QA uploads bucket (private; S3 API) without printing it.

    python tools/railway/qa_bucket.py put <file> <key>
    python tools/railway/qa_bucket.py get <key> <file>
    python tools/railway/qa_bucket.py delete <key>

Credentials from AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_REGION, UPLOADS_BUCKET and S3_ADDRESSING_STYLE (core-api's sealed values,
referenced by the qa-runner service; locally, from `railway bucket credentials`).
"""
import os
import sys

import boto3
from botocore.config import Config


def client():  # type: ignore[no-untyped-def]
    style = os.environ.get("S3_ADDRESSING_STYLE", "virtual").lower()
    style = "virtual" if style.startswith("virtual") else style  # Railway says "virtual-host"
    return boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"], region_name=os.environ.get("AWS_REGION"),
                        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                        config=Config(s3={"addressing_style": style}))


def main(op: str, *args: str) -> None:
    bucket = os.environ["UPLOADS_BUCKET"]
    s3 = client()
    if op == "put":
        src, key = args
        s3.upload_file(src, bucket, key)
        print(f"stored {key} in the uploads bucket")
    elif op == "get":
        key, dst = args
        s3.download_file(bucket, key, dst)
        os.chmod(dst, 0o600)
        print(f"fetched {key}")
    elif op == "delete":
        (key,) = args
        s3.delete_object(Bucket=bucket, Key=key)
        print(f"deleted {key}")
    else:
        raise SystemExit(f"unknown operation {op}")


if __name__ == "__main__":
    main(*sys.argv[1:])
