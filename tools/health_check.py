import sys

import requests

try:
    port = sys.argv[1]
except IndexError:
    print("Usage: python health_check.py <port>")
    sys.exit(1)

try:
    requests.get(f"http://localhost:{port}/status")
except requests.ConnectionError:
    print("Unable to connect to the server")
    sys.exit(1)
