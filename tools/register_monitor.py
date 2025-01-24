import sys
from pathlib import Path

import requests


def main() -> None:
    """Register a monitor, sending a request to the application.
    Usage: python register_monitor.py <monitor_name> <monitor_file> [<additional_file>, ...]
    """
    monitor_name = sys.argv[1]
    monitor_file = Path(sys.argv[2])
    additional_files = [Path(file_path) for file_path in sys.argv[3:]]

    with open(monitor_file, "r") as file:
        monitor_code = file.read()

    additional_files_content = {}
    for file_path in additional_files:
        with open(file_path, "r") as file:
            additional_files_content[file_path.stem] = file.read()

    result = requests.post(
        f"http://localhost:8000/monitor/register/{monitor_name}",
        json={
            "monitor_code": monitor_code,
            "additional_files": additional_files,
        }
    )
    print(result.json())


if __name__ == "__main__":
    main()
