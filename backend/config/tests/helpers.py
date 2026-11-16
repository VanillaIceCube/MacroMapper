import json

import requests

BACKEND = "anymail.backends.resend.EmailBackend"


PRIVATE = "recipient@example.test reset?token=private-token sk-private-key private-body"


def api_response(status=200, body=None):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body or {"id": "synthetic-message-id"}).encode()
    response.headers["Content-Type"] = "application/json"
    return response
