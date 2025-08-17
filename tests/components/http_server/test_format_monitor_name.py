import pytest

import components.http_server.format_monitor_name as format_monitor_name


@pytest.mark.parametrize(
    "input_name, expected_output",
    [
        ("simple_monitor", "simple_monitor"),
        ("UPPERCASE", "uppercase"),
        ("MixedCase", "mixedcase"),
        ("monitor.name", "monitor_name"),
        ("a.b.c.d", "a_b_c_d"),
        ("monitor name", "monitor_name"),
        ("monitor._name", "monitor_name"),
        ("monitor_._name", "monitor_name"),
        ("monitor____name", "monitor_name"),
        ("_monitor_", "monitor"),
        ("__monitor__", "monitor"),
        ("___monitor___", "monitor"),
        ("My.Monitor-Name@123", "my_monitorname123"),
        ("Service.Monitor_v2.1", "service_monitor_v2_1"),
        ("test...monitor", "test_monitor"),
        ("Monitor--.--Name", "monitor_name"),
        ("API_Gateway.Health-Check@v1", "api_gateway_healthcheckv1"),
        ("", ""),
        (".", ""),
        ("..", ""),
        ("...", ""),
        ("___", ""),
        ("123", "123"),
        ("monitor123", "monitor123"),
        ("123monitor", "123monitor"),
    ],
)
def test_format_monitor_name(input_name, expected_output):
    """'format_monitor_name' should format the monitor name correctly"""
    assert format_monitor_name.format_monitor_name(input_name) == expected_output
