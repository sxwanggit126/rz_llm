import os
from botocore.exceptions import ClientError
from loguru import logger
from app.tools.data_source.a_s3_connector import AS3Client
from typing import List, Optional


class S3Service:

    def __init__(self):
        self.default_bucket = os.getenv("AWS_DEFAULT_BUCKET")
        self.s3_client = AS3Client()

    async def exist_object(self, object_name, bucket_name=None):
        if bucket_name is None:
            bucket_name = self.default_bucket
        try:
            async with self.s3_client.get_s3_client() as s3:
                resposne = await s3.head_object(Bucket=bucket_name, Key=object_name)
                logger.info(f"Object '{object_name}' exists in bucket '{bucket_name}'.")
                return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                logger.info(f"Object '{object_name}' does not exist in bucket '{bucket_name}'.")
            return False

    async def upload_object(self, object_name, content, bucket_name=None):
        """Upload object to S3 asynchronously."""
        if bucket_name is None:
            bucket_name = self.default_bucket
        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.put_object(Bucket=bucket_name, Key=object_name, Body=content)
                logger.info(f"Successfully uploaded object '{object_name}' to bucket '{bucket_name}'.")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload object '{object_name}' to bucket '{bucket_name}': {e}")
            return False
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while uploading object '{object_name}' to bucket '{bucket_name}'.")
            return False

    async def get_object(self, object_name, bucket_name=None):
        """Get an object from S3 asynchronously."""
        if bucket_name is None:
            bucket_name = self.default_bucket

        if not object_name or not bucket_name:
            logger.error("The object name or bucket name cannot be empty")
            return None

        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.get_object(Bucket=bucket_name, Key=object_name)
                content = await response['Body'].read()
                object_size = response['ContentLength']
                object_metadata = response['Metadata']
                logger.info(
                    f"Successfully retrieved object {object_name} from bucket {bucket_name}. Size: {object_size}. Metadata: {object_metadata}")
                return content
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                logger.error(f"Object {object_name} not found in bucket {bucket_name}")
            else:
                logger.error(f"Failed to retrieve object {object_name} from bucket {bucket_name}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while trying to retrieve object {object_name} from bucket {bucket_name}: {e}")
            return None

    async def upload_file(self, file_path, bucket_name=None, object_name=None):
        """Upload file to S3 asynchronously and optionally generate a preview URL."""
        if bucket_name is None:
            bucket_name = self.default_bucket
        if not file_path or not bucket_name:
            logger.error("The file path or bucket name cannot be empty")
            return False
        if object_name is None:
            object_name = file_path
        try:
            with open(file_path, 'rb') as data:
                async with self.s3_client.get_s3_client() as s3:
                    resposne = await s3.put_object(Bucket=bucket_name, Key=object_name, Body=data)
                    logger.info(f"The file {file_path} has been successfully uploaded to {bucket_name}/{object_name}")
                    return True
        except FileNotFoundError:
            logger.error(f"The file {file_path} does not exist")
            return False
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    async def download_file(self, object_name, file_path, bucket_name=None):
        """Download files from S3 asynchronously."""
        if bucket_name is None:
            bucket_name = self.default_bucket
        if not bucket_name or not object_name or not file_path:
            logger.error("Bucket name, object name, or file path cannot be empty")
            return False
        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.get_object(Bucket=bucket_name, Key=object_name)
                content = await response['Body'].read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                logger.info(f"The files {bucket_name}/{object_name} have been successfully downloaded to {file_path}")
                return True
        except Exception as e:
            logger.error(f"Download file failed: {e}")
            return False

    async def list_objects(self, bucket_name=None, prefix: str = "", max_keys: int = 1000):
        """
        列出S3对象，支持prefix过滤

        Args:
            bucket_name: 存储桶名称
            prefix: 对象前缀，用于过滤
            max_keys: 最大返回数量

        Returns:
            对象键列表
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        if not bucket_name:
            logger.error("Bucket name cannot be empty")
            return []

        try:
            async with self.s3_client.get_s3_client() as s3:
                # 使用prefix参数进行服务端过滤
                params = {
                    'Bucket': bucket_name,
                    'MaxKeys': max_keys
                }

                if prefix:
                    params['Prefix'] = prefix

                response = await s3.list_objects_v2(**params)

                if 'Contents' not in response:
                    logger.info(f"No objects found in bucket {bucket_name} with prefix '{prefix}'")
                    objects = []
                else:
                    objects = [content['Key'] for content in response['Contents']]
                    logger.info(
                        f"Successfully listed {len(objects)} objects in bucket {bucket_name} with prefix '{prefix}'")

                return objects

        except Exception as e:
            logger.error(f"Failed to list objects with prefix '{prefix}': {e}")
            return []

    async def list_objects_with_details(self, bucket_name=None, prefix: str = "", max_keys: int = 1000):
        """
        列出S3对象及其详细信息（大小、修改时间等）

        Args:
            bucket_name: 存储桶名称
            prefix: 对象前缀
            max_keys: 最大返回数量

        Returns:
            包含详细信息的对象列表
        """
        if bucket_name is None:
            bucket_name = self.default_bucket
        if not bucket_name:
            logger.error("Bucket name cannot be empty")
            return []

        try:
            async with self.s3_client.get_s3_client() as s3:
                params = {
                    'Bucket': bucket_name,
                    'MaxKeys': max_keys
                }

                if prefix:
                    params['Prefix'] = prefix

                response = await s3.list_objects_v2(**params)

                if 'Contents' not in response:
                    logger.info(f"No objects found in bucket {bucket_name} with prefix '{prefix}'")
                    objects = []
                else:
                    objects = []
                    for content in response['Contents']:
                        objects.append({
                            'key': content['Key'],
                            'size': content['Size'],
                            'last_modified': content['LastModified'].isoformat(),
                            'etag': content.get('ETag', '').strip('"')
                        })

                    logger.info(
                        f"Successfully listed {len(objects)} objects with details in bucket {bucket_name} with prefix '{prefix}'")

                return objects

        except Exception as e:
            logger.error(f"Failed to list objects with details for prefix '{prefix}': {e}")
            return []

    async def delete_object(self, object_name, bucket_name=None):
        """Delete objects on S3 asynchronously."""
        if bucket_name is None:
            bucket_name = self.default_bucket
        if not bucket_name or not object_name:
            logger.error("Bucket name or object name cannot be empty")
            return False
        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.delete_object(Bucket=bucket_name, Key=object_name)
                logger.info(f"Object {bucket_name}/{object_name} successfully deleted")
                return True
        except Exception as e:
            logger.error(f"fail to delete object: {e}")
            return False

    async def create_bucket(self, bucket_name):
        """Create a bucket on S3 asynchronously."""
        if not bucket_name:
            logger.error("Bucket name cannot be empty")
            return False
        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.create_bucket(Bucket=bucket_name)
                logger.info(f"Bucket {bucket_name} created successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to create bucket: {e}")
            return False

    async def get_file_preview_url(self, object_name, bucket_name=None, expiration=3600):
        """Generate a presigned URL to share an S3 object asynchronously."""
        if bucket_name is None:
            bucket_name = self.default_bucket
        try:
            async with self.s3_client.get_s3_client() as s3:
                response = await s3.generate_presigned_url('get_object',
                                                           Params={'Bucket': bucket_name, 'Key': object_name},
                                                           ExpiresIn=expiration)
            logger.info(f"Generated presigned URL for {bucket_name}/{object_name}")
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {bucket_name}/{object_name}: {e}")
            return None