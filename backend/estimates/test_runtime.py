"""Exercise the actual Dockerfile Gunicorn command on Linux with fake SDK I/O."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = """
import json, os, time
from types import SimpleNamespace
import django
django.setup()
from django.test import override_settings
from estimates.provider import OpenAIMealEstimationProvider, EstimationProviderError

def application(environ, start_response):
    path = environ['PATH_INFO']
    status = '200 OK'
    if path != '/health':
        delay = 35 if path == '/slow' else 1
        budget = 110 if path == '/slow' else 0.1
        def parse(**kwargs):
            time.sleep(delay)
            return SimpleNamespace()
        client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
        with override_settings(OPENAI_MEAL_ESTIMATION_TIMEOUT=budget):
            try:
                OpenAIMealEstimationProvider(client=client)._parse(model='fake')
            except EstimationProviderError:
                status = '503 Service Unavailable'
    start_response(status, [('Content-Type', 'application/json')])
    return [json.dumps({'pid': os.getpid()}).encode()]
"""


@unittest.skipIf(
    sys.platform == "win32", "Gunicorn requires POSIX; run in Linux CI/Docker"
)
class GunicornDeadlineTests(unittest.TestCase):
    def test_slow_call_survives_old_worker_deadline_and_health_stays_responsive(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "timeout_fixture.py").write_text(FIXTURE)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            command = next(
                json.loads(line.removeprefix("CMD "))
                for line in (ROOT / "Dockerfile").read_text().splitlines()
                if line.startswith("CMD ")
            )
            command[0:2] = [
                sys.executable,
                "-m",
                "gunicorn",
                "timeout_fixture:application",
            ]
            command[command.index("--bind") + 1] = f"127.0.0.1:{port}"
            command += ["--pythonpath", str(target)]
            env = {
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "app.settings",
                "DJANGO_DEBUG": "1",
                "DJANGO_SECRET_KEY": "synthetic-runtime-test-key",
                "DJANGO_SQLITE_PATH": str(target / "test.sqlite3"),
                "OPENAI_MEAL_ESTIMATION_TIMEOUT": "110",
            }
            env.pop("GUNICORN_CMD_ARGS", None)
            url = f"http://127.0.0.1:{port}"

            def request(path, timeout=45):
                try:
                    response = urllib.request.urlopen(url + path, timeout=timeout)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return response.status, json.loads(response.read())

            with (target / "server.log").open("w+") as log:
                process = subprocess.Popen(
                    command, cwd=ROOT, env=env, stdout=log, stderr=log
                )
                try:
                    for _ in range(100):
                        if process.poll() is not None:
                            log.seek(0)
                            self.fail(log.read())
                        try:
                            status, body = request("/health", timeout=1)
                            break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        self.fail("Gunicorn did not start")
                    self.assertEqual(status, 200)
                    pid = body["pid"]
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        slow = executor.submit(request, "/slow")
                        time.sleep(1)
                        started = time.monotonic()
                        self.assertEqual(
                            request("/health", timeout=2), (200, {"pid": pid})
                        )
                        self.assertLess(time.monotonic() - started, 2)
                        self.assertEqual(slow.result(timeout=40), (200, {"pid": pid}))
                    self.assertEqual(request("/deadline"), (503, {"pid": pid}))
                    self.assertEqual(request("/health"), (200, {"pid": pid}))
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                log.seek(0)
                self.assertNotIn("WORKER TIMEOUT", log.read())
