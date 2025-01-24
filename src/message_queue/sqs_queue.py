import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, cast

import aioboto3
from aiobotocore.session import AioBaseClient
from botocore.exceptions import ClientError

from configs import SQSQueueConfig, configs
from message_queue.protocols import Message

_logger = logging.getLogger("sqs_queue")


class SQSMessage:
    message: dict[str, Any]
    id: str

    def __init__(self, message: dict[str, Any]) -> None:
        self.message = message
        self.id = message["ReceiptHandle"]

    @property
    def content(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.message["Body"]))


def _get_aws_config(application_queue: SQSQueueConfig) -> dict[str, str | None]:
    """Get the AWS credentials from the environment variables"""
    aws_config = {
        "region_name": application_queue.region,
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "aws_session_token": os.environ.get("AWS_SESSION_TOKEN"),
    }
    if os.environ.get("AWS_ENDPOINT_URL") is not None:
        aws_config["endpoint_url"] = os.environ.get("AWS_ENDPOINT_URL")

    return aws_config


@asynccontextmanager
async def _aws_client(aws_config: dict[str, str | None]) -> AsyncGenerator[AioBaseClient, None]:
    """Create a AWS client context manager to be used in the request"""
    session = aioboto3.Session()
    async with session.client("sqs", **aws_config) as client:
        yield client


async def _create_queue(client: AioBaseClient, queue_name: str) -> None:
    """Create a queue in the AWS SQS"""
    _logger.info("Queue doesn't exists, creating")
    response = await client.create_queue(QueueName=queue_name)
    _logger.info(f"Queue created: {str(response)}")


class SQSQueue:
    _application_queue: SQSQueueConfig
    _aws_config: dict[str, str | None]

    def __init__(self, application_queue: SQSQueueConfig) -> None:
        self._application_queue = application_queue
        self._aws_config = _get_aws_config(application_queue)

    async def init(self) -> None:
        """Test if the AWS SQS queue already exists and, if not, try to create if configured to"""
        _logger.info("SQS queue setup")

        queue_name = self._application_queue.name

        async with _aws_client(self._aws_config) as client:
            try:
                _logger.info("Checking queue")
                await client.get_queue_url(QueueName=queue_name)
            except ClientError as e:
                if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
                    raise  # pragma: no cover

                if not self._application_queue.create_queue:
                    raise RuntimeError(
                        "AWS SQS queue must exist or allow the application to create"
                    )

                await _create_queue(client, queue_name)

    async def send_message(self, type: str, payload: dict[str, Any]) -> None:
        """Send a message to the queue"""
        async with _aws_client(self._aws_config) as client:
            await client.send_message(
                QueueUrl=self._application_queue.url,
                MessageBody=json.dumps(
                    {
                        "type": type,
                        "payload": payload,
                    }
                ),
            )

    async def get_message(self) -> Message | None:
        """Get a message from the queue"""
        async with _aws_client(self._aws_config) as client:
            response = await client.receive_message(
                QueueUrl=self._application_queue.url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=configs.queue_wait_message_time,
                VisibilityTimeout=2 * configs.queue_visibility_time,
            )

            if "Messages" in response:
                return SQSMessage(response["Messages"][0])

        return None

    async def change_visibility(self, message: Message) -> None:
        """Change the visibility time for a message in the queue"""
        async with _aws_client(self._aws_config) as client:
            await client.change_message_visibility(
                QueueUrl=self._application_queue.url,
                ReceiptHandle=message.id,
                VisibilityTimeout=2 * configs.queue_visibility_time,
            )

    async def delete_message(self, message: Message) -> None:
        """Delete a message from the queue"""
        async with _aws_client(self._aws_config) as client:
            await client.delete_message(
                QueueUrl=self._application_queue.url,
                ReceiptHandle=message.id,
            )
