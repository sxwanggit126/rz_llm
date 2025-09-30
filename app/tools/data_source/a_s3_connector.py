"""
AWS S3 Connector Module

This module provides an asynchronous S3 client wrapper using aioboto3.
It implements a singleton pattern to ensure only one S3 client instance exists
throughout the application lifecycle.

The module includes:
- AS3Client: A singleton class that manages S3 client connections
- Async S3 operations support through aioboto3
- Centralized logging for S3 operations
"""

import aioboto3
import aioboto3.session
from app.tools.data_source.signalton_meta import SingletonMeta
from loguru import logger


class AS3Client(metaclass=SingletonMeta):
    """
    Asynchronous S3 Client wrapper using singleton pattern.

    This class provides a centralized way to manage S3 client connections
    using aioboto3. It implements the singleton pattern to ensure only
    one instance exists throughout the application lifecycle, preventing
    resource waste and connection overhead.

    Attributes:
        s3_session (aioboto3.Session): The aioboto3 session instance
            used to create S3 clients.
    """

    def __init__(self):
        """
        Initialize the AS3Client instance.

        Creates a new aioboto3 session that will be used to generate
        S3 clients for async operations.
        """
        self.s3_session = aioboto3.Session()

    def get_s3_client(self):
        """
        Get an S3 client instance for async operations.

        Returns:
            aioboto3.client: An async S3 client instance that can be used
                for performing S3 operations like upload, download, list,
                delete, etc.
        """
        return self.s3_session.client("s3")
