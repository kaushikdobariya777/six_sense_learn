import logging
import boto3
from botocore.exceptions import ClientError

from sixsense import settings


class S3Service(object):
    def __init__(
        self, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    ) -> None:
        if aws_access_key_id:
            self.s3_client = boto3.client(
                "s3", aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key
            )
        else:
            self.s3_client = boto3.client("s3")

    def generate_pre_signed_post(self, key):
        try:
            response = self.s3_client.generate_presigned_post(settings.AWS_STORAGE_BUCKET_NAME, key, ExpiresIn=86400)
        except ClientError as e:
            logging.error(e)
            return None
        return response

    def generate_pre_signed_url(self, key):
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object", Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key}, ExpiresIn=86400
            )
        except ClientError as e:
            logging.error(e)
            return None
        return url

    def list_objects(self, prefix):
        return self.s3_client.list_objects_v2(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=prefix)["Contents"]

    def upload_file(self, file_path, key, bucket=settings.AWS_STORAGE_BUCKET_NAME):
        try:
            response = self.s3_client.upload_file(file_path, bucket, key)
        except ClientError as e:
            logging.error(e)
            return None
        return response

    def delete_file(self, key, bucket=settings.AWS_STORAGE_BUCKET_NAME):
        try:
            response = self.s3_client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            logging.error(e)
            return None
        return response

    def check_if_key_exists(self, key, bucket=settings.AWS_STORAGE_BUCKET_NAME):
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False


class SqsService(object):
    def __init__(self, queue_url) -> None:
        sqs_resource = boto3.resource("sqs", region_name=settings.IMAGE_HANDLER_QUEUE_REGION_NAME)
        self.sqs_client = sqs_resource.Queue(queue_url)

    def send_message(self, message):
        return self.sqs_client.send_message(MessageBody=message)
