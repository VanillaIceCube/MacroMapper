"""Select ASGI only for the explicitly enabled MCP profile."""

import os


def command():
    if os.getenv("DJANGO_MCP_ENABLED", "0") == "1":
        return [
            "uvicorn",
            "app.asgi:application",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            "1",
            "--no-proxy-headers",
        ]
    return [
        "gunicorn",
        "app.wsgi:application",
        "--bind",
        "0.0.0.0:8000",
        "--workers",
        "1",
        "--worker-class",
        "gthread",
        "--threads",
        "4",
        "--timeout",
        "120",
    ]


if __name__ == "__main__":
    args = command()
    os.execvp(args[0], args)
