import pytest

from monitor_utils import read_file


def test_read_file():
    """'read_file' should open a file relative to the file where the function was called"""
    content = read_file("sample_file.txt")
    assert content == "Test file content\n"


@pytest.mark.parametrize("mode", ["a", "w", "wb"])
def test_read_file_invalid_mode(mode):
    """'read_file' should raise a ValueError if an invalid mode is passed"""
    with pytest.raises(ValueError):
        read_file("sample_file.txt", mode=mode)
