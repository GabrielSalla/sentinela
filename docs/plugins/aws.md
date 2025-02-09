# AWS Plugin
The AWS plugin provides a Queue implementation for AWS SQS (Simple Queue Service) and an asynchronous client to interact with AWS services using the `aiobotocore` module, which is an asynchronous version of the `boto3` module.

This plugin allows the use of different credentials for different services if desired. If any monitor uses the AWS client, it's recommended to use a different credential than the application's main credential.

## Enabling
To enable the AWS plugin, set the environment variable `SENTINELA_PLUGINS` with the value `aws`.

## Environment variables
Credentials are selected by a **name**, which indicates which environment variable should be used. The variables that have this setting will have the placeholder `{name}` in their name. The credential name **must be in uppercase letters**.

The following environment variables are used by the AWS plugin:
- `AWS_ENDPOINT_URL`: Specifies the AWS endpoint to be used for local testing, without the need for a real SQS queue. When using the `motoserver` container as an AWS mock, it should be `http://motoserver:5000`. Do not set this environment variable when using a production SQS queue.
- `AWS_{name}_REGION`: Specifies the region to be used with this credential. This environment variable will only be used when one is not specified in the client initialization.
- `AWS_{name}_ACCESS_KEY_ID`, `AWS_{name}_SECRET_ACCESS_KEY` and `AWS_{name}_SESSION_TOKEN`: Specify the service credentials to access the AWS SQS queue. If the credentials do not include the session token, the `AWS_SESSION_TOKEN` environment variable should not be set.

When using the AWS plugin queue, the expected name for the environment variables is `APPLICATION`, indicating it's the main application credentials. The following example shows how to set the environment variables for the AWS plugin:

```
AWS_APPLICATION_REGION=us-east-1
AWS_APPLICATION_ACCESS_KEY_ID=SOME_ACCESS_KEY_ID
AWS_APPLICATION_SECRET_ACCESS_KEY=SOME_SECRET_ACCESS_KEY
```

## Queue
To use the AWS plugin queue, configure its parameters in the configuration file under the setting `application_queue`.

The queue settings are:
- `type`: The plugin type, which should be `plugin.aws.sqs`.
- `name`: The queue name.
- `url`: The queue URL.
- `region`: The region where the queue is located. If not configured, the region will be taken from the environment variables for the provided credentials.
- `create_queue`: A flag to indicate if the queue should be created if it doesn't exist. This flag is mainly used for testing purposes and should be set to `false` in production environments. Defaults to `false`.
- `queue_wait_message_time`: Time, in seconds, to wait for a message. Higher values will increase the application's shutdown time. Defaults to `2`.
- `queue_visibility_time`: Time to wait, in seconds, to change a message's visibility in the queue. Must be lower than the default queue's visibility time, or a message might become visible before it finishes processing. Defaults to `15`.

An example of the queue configuration is shown below:
```yaml
application_queue:
  type: plugin.aws.sqs
  name: app
  url: http://motoserver:5000/123456789012/app
  region: us-east-1
  queue_wait_message_time: 2
  queue_visibility_time: 15
```

## Client
The AWS plugin client can be used to interact with AWS services. The client is initialized with the desired credentials and region using an async context manager.

```python
async def aws_client(
    credential_name: str, service: str, region_name: str | None = None
) -> AsyncGenerator[AioBaseClient, None]
```

The `aws_client` function parameters are:
- `credential_name`: The name of the credentials to be used, which will have environment variables set for it.
- `service`: The AWS service to be used. Example: `sqs`, `s3`, `athena`.
- `region_name`: The region to be used with this client. If not specified, the region will be taken from the environment variables for the provided credentials.

The following example shows how to use the client to interact with the AWS S3 service:

```python
from plugins.aws.client import aws_client

async with aws_client("application", "s3") as client:
    response = await client.list_buckets()
    print(response)
```
