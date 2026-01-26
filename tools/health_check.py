import sys

import requests


def main() -> None:
    try:
        port = sys.argv[1]
    except IndexError:
        print("Usage: health_check <port>")
        return

    try:
        requests.get(f"http://localhost:{port}/status")
    except requests.ConnectionError:
        print("Unable to connect to the server")
        return


if __name__ == "__main__":
    main()
