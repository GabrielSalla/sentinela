import pytest

import plugins.aws.client as aws_client

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("name", ["ABC", "DEF"])
@pytest.mark.parametrize("region", ["us-east-1", "us-east-2"])
@pytest.mark.parametrize("access_key_id", ["key_id", "other_key"])
@pytest.mark.parametrize("access_key", ["access_key", "pass"])
@pytest.mark.parametrize("session_token", ["session_token", "token", None])
@pytest.mark.parametrize("endpoint_url", ["http://localhost:4566", "somewhere.com", None])
async def test_get_aws_config(
    monkeypatch, name, region, access_key_id, access_key, session_token, endpoint_url
):
    """'_get_aws_function' should return the AWS credentials from the environment variables,
    validating the required ones"""
    monkeypatch.setenv(f"AWS_{name}_REGION", region)
    monkeypatch.setenv(f"AWS_{name}_ACCESS_KEY_ID", access_key_id)
    monkeypatch.setenv(f"AWS_{name}_SECRET_ACCESS_KEY", access_key)
    if session_token:
        monkeypatch.setenv(f"AWS_{name}_SESSION_TOKEN", session_token)
    else:
        monkeypatch.delenv(f"AWS_{name}_SESSION_TOKEN", raising=False)
    if endpoint_url:
        monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint_url)
    else:
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

    aws_app_config = aws_client._get_aws_config("application")
    if endpoint_url:
        assert aws_app_config.pop("endpoint_url") == endpoint_url
    assert aws_app_config == {
        "region_name": "us-east-1",
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
        "aws_session_token": "test",
    }

    aws_config = aws_client._get_aws_config(name)
    assert aws_config["region_name"] == region
    assert aws_config["aws_access_key_id"] == access_key_id
    assert aws_config["aws_secret_access_key"] == access_key
    if session_token:
        assert aws_config["aws_session_token"] == session_token
    else:
        assert "aws_session_token" not in aws_config
    if endpoint_url:
        assert aws_config["endpoint_url"] == endpoint_url
    else:
        assert "endpoint_url" not in aws_config


async def test_get_aws_config_no_region(monkeypatch):
    """'_get_aws_function' should raise a ValueError when the region is not found"""
    monkeypatch.delenv("AWS_APPLICATION_REGION")
    monkeypatch.setenv("AWS_APPLICATION_ACCESS_KEY_ID", "app_access_key_id")
    monkeypatch.setenv("AWS_APPLICATION_SECRET_ACCESS_KEY", "app_access_key")
    monkeypatch.setenv("AWS_APPLICATION_SESSION_TOKEN", "app_session_token")
    monkeypatch.setenv("AWS_APPLICATION_ENDPOINT_URL", "app_endpoint_url")

    expected_message = "AWS region name not found for 'application'"
    with pytest.raises(ValueError, match=expected_message):
        aws_client._get_aws_config("application")


async def test_get_aws_config_no_access_key_id(monkeypatch):
    """'_get_aws_function' should raise a ValueError when the access key ID is not found"""
    monkeypatch.setenv("AWS_APPLICATION_REGION", "app_region")
    monkeypatch.delenv("AWS_APPLICATION_ACCESS_KEY_ID")
    monkeypatch.setenv("AWS_APPLICATION_SECRET_ACCESS_KEY", "app_access_key")
    monkeypatch.setenv("AWS_APPLICATION_SESSION_TOKEN", "app_session_token")
    monkeypatch.setenv("AWS_APPLICATION_ENDPOINT_URL", "app_endpoint_url")

    expected_message = "AWS credential access key ID not found for 'application'"
    with pytest.raises(ValueError, match=expected_message):
        aws_client._get_aws_config("application")


async def test_get_aws_config_no_secret_access_key(monkeypatch):
    """'_get_aws_function' should raise a ValueError when the secret access key is not found"""
    monkeypatch.setenv("AWS_APPLICATION_REGION", "app_region")
    monkeypatch.setenv("AWS_APPLICATION_ACCESS_KEY_ID", "app_access_key_id")
    monkeypatch.delenv("AWS_APPLICATION_SECRET_ACCESS_KEY")
    monkeypatch.setenv("AWS_APPLICATION_SESSION_TOKEN", "app_session_token")
    monkeypatch.setenv("AWS_APPLICATION_ENDPOINT_URL", "app_endpoint_url")

    expected_message = "AWS credential secret access key not found for 'application'"
    with pytest.raises(ValueError, match=expected_message):
        aws_client._get_aws_config("application")


async def test_aws_client():
    """'aws_client' should create a AWS client context manager. As motoserver do not execute the
    query, we don't care about the result"""
    async with aws_client.aws_client("application", "athena") as client:
        response = await client.start_query_execution(QueryString="select 1")
        result = await client.get_query_results(QueryExecutionId=response["QueryExecutionId"])
        assert result["ResultSet"]["Rows"] == []
