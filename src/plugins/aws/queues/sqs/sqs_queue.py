import json
import logging
from typing import Any, Literal, cast

from aiobotocore.session import AioBaseClient
from botocore.exceptions import ClientError
from pydantic.dataclasses import dataclass

from message_queue.protocols import Message

from ...client import aws_client

_logger = logging.getLogger("sqs_queue")


@dataclass
class SQSQueueConfig:
    type: Literal["plugin.aws.sqs"]
    name: str
    url: str
    region: str | None = None
    create_queue: bool = False
    queue_wait_message_time: int = 2
    queue_visibility_time: int = 15


class SQSMessage:
    message: dict[str, Any]
    id: str

    def __init__(self, message: dict[str, Any]) -> None:
        self.message = message
        self.id = message["ReceiptHandle"]

    @property
    def content(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.message["Body"]))


async def _create_queue(client: AioBaseClient, queue_name: str) -> None:
    """Create a queue in the AWS SQS"""
    _logger.info("Queue doesn't exists, creating")
    response = await client.create_queue(QueueName=queue_name)
    _logger.info(f"Queue created: {str(response)}")


class Queue:
    _config: SQSQueueConfig
    _aws_client_params: dict[str, str]

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = SQSQueueConfig(**config)
        self._aws_client_params = {
            "credential_name": "application",
            "service": "sqs",
        }
        if self._config.region:
            self._aws_client_params["region_name"] = self._config.region

    @property
    def queue_wait_message_time(self) -> int:
        return self._config.queue_wait_message_time

    async def init(self) -> None:
        """Test if the AWS SQS queue already exists and, if not, try to create if configured to"""
        _logger.info("SQS queue setup")

        queue_name = self._config.name

        async with aws_client(**self._aws_client_params) as client:
            try:
                _logger.info("Checking queue")
                await client.get_queue_url(QueueName=queue_name)
            except ClientError as e:
                if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
                    raise  # pragma: no cover

                if not self._config.create_queue:
                    raise RuntimeError(
                        "AWS SQS queue must exist or allow the application to create"
                    )

                await _create_queue(client, queue_name)

    async def send_message(self, type: str, payload: dict[str, Any]) -> None:
        """Send a message to the queue"""
        async with aws_client(**self._aws_client_params) as client:
            await client.send_message(
                QueueUrl=self._config.url,
                MessageBody=json.dumps(
                    {
                        "type": type,
                        "payload": payload,
                    }
                ),
            )

    async def get_message(self) -> Message | None:
        """Get a message from the queue"""
        async with aws_client(**self._aws_client_params) as client:
            response = await client.receive_message(
                QueueUrl=self._config.url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=self._config.queue_wait_message_time,
                VisibilityTimeout=2 * self._config.queue_visibility_time,
            )

            if "Messages" in response:
                return SQSMessage(response["Messages"][0])

        return None

    async def change_visibility(self, message: Message) -> None:
        """Change the visibility time for a message in the queue"""
        async with aws_client(**self._aws_client_params) as client:
            await client.change_message_visibility(
                QueueUrl=self._config.url,
                ReceiptHandle=message.id,
                VisibilityTimeout=2 * self._config.queue_visibility_time,
            )

    async def delete_message(self, message: Message) -> None:
        """Delete a message from the queue"""
        async with aws_client(**self._aws_client_params) as client:
            await client.delete_message(
                QueueUrl=self._config.url,
                ReceiptHandle=message.id,
            )
