import pytest

import commands.validations as validations
from exceptions.http_server import AlertNotFoundError, IssueNotFoundError, MonitorNotFoundError
from models import Alert, Issue, Monitor

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_validate_monitor_request(sample_monitor: Monitor):
    """'validate_monitor_request' should return monitor if found"""
    result = await validations.validate_monitor_request(sample_monitor.name)
    assert result.id == sample_monitor.id


async def test_validate_monitor_request_not_found():
    """'validate_monitor_request' should raise a 'MonitorNotFoundError' exception when monitor not
    found"""
    with pytest.raises(MonitorNotFoundError, match="Monitor 'not_found' not found"):
        await validations.validate_monitor_request("not_found")


async def test_validate_alert_request(sample_monitor: Monitor):
    """'validate_alert_request' should return alert if found"""
    alert = await Alert.create(monitor_id=sample_monitor.id)
    result = await validations.validate_alert_request(alert.id)
    assert result.id == alert.id


async def test_validate_alert_request_not_found():
    """'validate_alert_request' should raise a 'AlertNotFoundError' exception when alert not
    found"""
    with pytest.raises(AlertNotFoundError, match="Alert '999999999' not found"):
        await validations.validate_alert_request(999999999)


async def test_validate_issue_request(sample_monitor: Monitor):
    """'validate_issue_request' should return issue if found"""
    issue = await Issue.create(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})
    result = await validations.validate_issue_request(issue.id)
    assert result.id == issue.id


async def test_validate_issue_request_not_found():
    """'validate_issue_request' should raise a 'IssueNotFoundError' exception when issue not
    found"""
    with pytest.raises(IssueNotFoundError, match="Issue '999999999' not found"):
        await validations.validate_issue_request(999999999)
