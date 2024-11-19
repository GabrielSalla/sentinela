import asyncio

import uvloop


def test_loop():
    """Test that the loop being used with asyncio is an instance of 'uvloop.Loop'."""
    loop = asyncio.new_event_loop()
    assert isinstance(loop, uvloop.Loop)
