import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, cast

import aioboto3
from aiobotocore.session import AioBaseClient
from botocore.exceptions import ClientError

from src.configs import configs

_logger = logging.getLogger("sqs_queue")


class Message:
    message: dict[str, Any]
    receipt_handle: str

    def __init__(self, message: dict[str, Any]):
        self.message = message
        self.receipt_handle = message["ReceiptHandle"]

    @property
    def content(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.message["Body"]))


def _get_aws_config():
    """Get the AWS credentials from the environment variables"""
    aws_config = {
        "region_name": configs.application_queue["region"],
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "aws_session_token": os.environ.get("AWS_SESSION_TOKEN"),
    }
    if os.environ.get("AWS_ENDPOINT_URL") is not None:
        aws_config["endpoint_url"] = os.environ.get("AWS_ENDPOINT_URL")

    return aws_config


@asynccontextmanager
async def _aws_client() -> AsyncGenerator[AioBaseClient, None]:
    """Create a AWS client context manager to be used in the request"""
    session = aioboto3.Session()
    async with session.client("sqs", **_get_aws_config()) as client:
        yield client


async def _create_queue(client: AioBaseClient, queue_name: str):
    """Create a queue in the AWS SQS"""
    _logger.info("Queue doesn't exists, creating")
    response = await client.create_queue(QueueName=queue_name)
    _logger.info(f"Queue created: {str(response)}")


async def init():
    """Test if the AWS SQS queue already exists and, if not, try to create if configured to"""
    _logger.info("SQS queue setup")

    queue_name = configs.application_queue["name"]

    async with _aws_client() as client:
        try:
            _logger.info("Checking queue")
            await client.get_queue_url(QueueName=queue_name)
        except ClientError as e:
            if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
                raise  # pragma: no cover

            if not configs.application_queue["create_queue"]:
                raise RuntimeError("AWS SQS queue must exist or allow the application to create")

            await _create_queue(client, queue_name)


async def send_message(type: str, payload: dict[str, Any]):
    """Send a message to the queue"""
    async with _aws_client() as client:
        await client.send_message(
            QueueUrl=configs.application_queue["url"],
            MessageBody=json.dumps(
                {
                    "type": type,
                    "payload": payload,
                }
            ),
        )


async def get_message() -> Message | None:
    """Get a message from the queue"""
    async with _aws_client() as client:
        response = await client.receive_message(
            QueueUrl=configs.application_queue["url"],
            MaxNumberOfMessages=1,
            WaitTimeSeconds=configs.queue_wait_message_time,
            VisibilityTimeout=2 * configs.queue_visibility_time,
        )

        if "Messages" in response:
            return Message(response["Messages"][0])

    return None


async def change_visibility(message: Message):
    """Change the visibility time for a message in the queue"""
    async with _aws_client() as client:
        await client.change_message_visibility(
            QueueUrl=configs.application_queue["url"],
            ReceiptHandle=message.receipt_handle,
            VisibilityTimeout=2 * configs.queue_visibility_time,
        )


async def delete_message(message: Message):
    """Delete a message from the queue"""
    async with _aws_client() as client:
        await client.delete_message(
            QueueUrl=configs.application_queue["url"],
            ReceiptHandle=message.receipt_handle,
        )
