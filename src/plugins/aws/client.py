import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiobotocore.session import AioBaseClient, get_session

REGION = "AWS_{credential_name}_REGION"
ACCESS_KEY_ID_PATTERN = "AWS_{credential_name}_ACCESS_KEY_ID"
SECRET_ACCESS_KEY_PATTERN = "AWS_{credential_name}_SECRET_ACCESS_KEY"
SESSION_TOKEN_PATTERN = "AWS_{credential_name}_SESSION_TOKEN"

_logger = logging.getLogger("plugin.aws.client")


def _get_aws_config(credential_name: str, region_name: str | None = None) -> dict[str, str]:
    """Get the AWS credentials from the environment variables"""
    if region_name is None:
        region_name = os.environ.get(REGION.format(credential_name=credential_name.upper()))
    if region_name is None:
        raise ValueError(f"AWS region name not found for '{credential_name}'")

    access_key_id = os.environ.get(
        ACCESS_KEY_ID_PATTERN.format(credential_name=credential_name.upper())
    )
    if access_key_id is None:
        raise ValueError(f"AWS credential access key ID not found for '{credential_name}'")

    secret_access_key = os.environ.get(
        SECRET_ACCESS_KEY_PATTERN.format(credential_name=credential_name.upper())
    )
    if secret_access_key is None:
        raise ValueError(f"AWS credential secret access key not found for '{credential_name}'")

    aws_config = {
        "region_name": region_name,
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
    }

    session_token = os.environ.get(
        SESSION_TOKEN_PATTERN.format(credential_name=credential_name.upper())
    )
    if session_token is not None:
        aws_config["aws_session_token"] = session_token

    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url is not None:
        aws_config["endpoint_url"] = endpoint_url

    return aws_config


@asynccontextmanager
async def aws_client(
    credential_name: str, service: str, region_name: str | None = None
) -> AsyncGenerator[AioBaseClient, None]:
    """
    Create a AWS client context manager to interact with AWS services.
    - `credential_name`: The name of the credentials to be used, which will have environment
    variables set for it.
    - `service`: The AWS service to be used. Example: `sqs`, `s3`, `athena`.
    - `region_name`: The region to be used with this client. If not specified, the region will be
    taken from the environment variables for the provided credentials.
    """
    aws_config = _get_aws_config(credential_name, region_name)
    session = get_session()
    async with session.create_client(service, **aws_config) as client:
        yield client
