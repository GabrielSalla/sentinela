from notifications.base_notification import BaseNotification


def test_base_notification():
    assert BaseNotification.min_priority_to_send == 5
