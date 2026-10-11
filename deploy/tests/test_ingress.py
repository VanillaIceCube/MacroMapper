"""Exercise the supplied vhost in disposable containers, never the live proxy."""

import json
import shutil
import ssl
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENSSL = shutil.which("openssl")
if not OPENSSL and Path("C:/Program Files/Git/usr/bin/openssl.exe").is_file():
    OPENSSL = "C:/Program Files/Git/usr/bin/openssl.exe"
STUB = """import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Cache-Control', 'public, max-age=300')
        self.end_headers()
        self.wfile.write(json.dumps({'service': os.environ['SERVICE'], 'path': self.path, 'proto': self.headers.get('X-Forwarded-Proto'), 'host': self.headers.get('Host'), 'forwarded_host': self.headers.get('X-Forwarded-Host')}).encode())
HTTPServer(('0.0.0.0', int(os.environ['PORT'])), Handler).serve_forever()
"""


@unittest.skipUnless(
    shutil.which("docker") and OPENSSL, "Docker and OpenSSL are needed"
)
class SharedIngressTests(unittest.TestCase):
    def docker(self, *args):
        return subprocess.run(
            ["docker", *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_start_without_macromapper_route_isolation_headers_and_restart(self):
        prefix = "macromapper-launch-test-" + uuid.uuid4().hex[:10]
        containers = []
        network = prefix + "-net"
        notoli_network = prefix + "-notoli"
        self.docker("network", "create", network)
        self.docker("network", "create", notoli_network)
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                certs = target / "certs"
                certs.mkdir()
                openssl_config = target / "openssl.cnf"
                openssl_config.write_text("[req]\ndistinguished_name=dn\n[dn]\n")
                subprocess.run(
                    [
                        OPENSSL,
                        "req",
                        "-config",
                        str(openssl_config),
                        "-x509",
                        "-newkey",
                        "rsa:2048",
                        "-nodes",
                        "-days",
                        "1",
                        "-subj",
                        "/CN=localhost",
                        "-keyout",
                        str(certs / "origin.key"),
                        "-out",
                        str(certs / "origin.pem"),
                    ],
                    check=True,
                    capture_output=True,
                )
                config = target / "conf"
                config.mkdir()
                # Notoli keeps its generic upstream names on its own network.
                for service, port_number in (("backend", "8000"), ("frontend", "80")):
                    name = prefix + "-notoli-" + service
                    containers.append(name)
                    self.docker(
                        "run",
                        "-d",
                        "--name",
                        name,
                        "--network",
                        notoli_network,
                        "--network-alias",
                        service,
                        "-e",
                        "SERVICE=notoli-" + service,
                        "-e",
                        "PORT=" + port_number,
                        "python:3.12-alpine",
                        "python",
                        "-u",
                        "-c",
                        STUB,
                    )
                (config / "default.conf").write_text(
                    "server { listen 80 default_server; listen 443 ssl default_server; server_name notoli.test; ssl_certificate /etc/nginx/certs/origin.pem; ssl_certificate_key /etc/nginx/certs/origin.key; location /auth/ { proxy_pass http://backend:8000; } location / { proxy_pass http://frontend:80; } }\n"
                )
                shutil.copyfile(
                    ROOT / "deploy/nginx-shared.conf", config / "macromapper.conf"
                )
                proxy = prefix + "-proxy"
                containers.append(proxy)
                self.docker(
                    "run",
                    "-d",
                    "--name",
                    proxy,
                    "--network",
                    notoli_network,
                    "-p",
                    "127.0.0.1::443",
                    "-v",
                    f"{config}:/etc/nginx/conf.d:ro",
                    "-v",
                    f"{certs}:/etc/nginx/certs:ro",
                    "nginx:alpine",
                )
                self.docker("network", "connect", network, proxy)
                # DNS names do not exist yet: Notoli must still be able to start.
                self.docker("exec", proxy, "nginx", "-t")
                port = json.loads(self.docker("inspect", proxy))[0]["NetworkSettings"][
                    "Ports"
                ]["443/tcp"][0]["HostPort"]
                # Certificate verification is disabled only for this generated local test certificate.
                context = ssl._create_unverified_context()

                def request(path, host="macromapper.judeandrewalaba.com"):
                    req = urllib.request.Request(
                        f"https://127.0.0.1:{port}{path}",
                        headers={
                            "Host": host,
                            "X-Forwarded-Proto": "http",
                            "X-Forwarded-Host": "attacker.invalid",
                        },
                    )
                    with urllib.request.urlopen(
                        req, context=context, timeout=8
                    ) as response:
                        return response.read(), response.headers

                def wait_for_request(path, host="macromapper.judeandrewalaba.com"):
                    for _ in range(29):
                        try:
                            return request(path, host)
                        except (urllib.error.URLError, TimeoutError):
                            time.sleep(1)
                    return request(path, host)

                self.assertEqual(
                    json.loads(wait_for_request("/", "notoli.test")[0])["service"],
                    "notoli-frontend",
                )
                # Start the actual merged production services with disposable stubs.
                for filename in ("docker-compose.yml", "docker-compose.shared.yml"):
                    shutil.copyfile(ROOT / "deploy" / filename, target / filename)
                (target / ".env").write_text(
                    "MACROMAPPER_BACKEND_IMAGE=python:3.12-alpine\nMACROMAPPER_FRONTEND_IMAGE=python:3.12-alpine\n"
                )
                (target / ".backend.env").touch()
                stub_compose = {
                    "services": {},
                    "networks": {"ingress": {"name": network}},
                }
                for service, port_number in (("backend", "8000"), ("frontend", "80")):
                    name = prefix + "-" + service
                    containers.append(name)
                    stub_compose["services"]["macromapper-" + service] = {
                        "container_name": name,
                        "environment": {"SERVICE": service, "PORT": port_number},
                        "command": ["python", "-u", "-c", STUB],
                    }
                # Avoid the real database bind in the backend test container.
                (target / "stubs.yml").write_text(json.dumps(stub_compose))
                (target / "no-database.yml").write_text(
                    "services:\n  macromapper-backend:\n    volumes: !reset []\n"
                )
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-p",
                        prefix,
                        "-f",
                        "docker-compose.yml",
                        "-f",
                        "docker-compose.shared.yml",
                        "-f",
                        "stubs.yml",
                        "-f",
                        "no-database.yml",
                        "up",
                        "-d",
                        "macromapper-backend",
                        "macromapper-frontend",
                    ],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                for service in ("backend", "frontend"):
                    aliases = json.loads(
                        self.docker("inspect", prefix + "-" + service)
                    )[0]["NetworkSettings"]["Networks"][network]["Aliases"]
                    self.assertIn("macromapper-" + service, aliases)
                    self.assertNotIn(service, aliases)
                # Wait for the test HTTP servers, with a bounded deadline.
                body, _ = wait_for_request("/diary")
                self.assertEqual(json.loads(body)["service"], "frontend")
                for path in (
                    "/auth/login/",
                    "/api/foods/?search=apple%20pie&limit=1",
                    "/admin/login/",
                    "/static/admin/css/base.css",
                ):
                    body, headers = request(path)
                    data = json.loads(body)
                    self.assertEqual(data["service"], "backend")
                    self.assertEqual(data["path"], path)
                    self.assertEqual(data["proto"], "https")
                    self.assertEqual(data["host"], "macromapper.judeandrewalaba.com")
                    self.assertIsNone(data["forwarded_host"])
                    if not path.startswith("/static/"):
                        self.assertEqual(headers["Cache-Control"], "no-store")
                self.docker("stop", prefix + "-backend")
                self.docker("restart", proxy)
                self.docker("exec", proxy, "nginx", "-t")
                port = json.loads(self.docker("inspect", proxy))[0]["NetworkSettings"][
                    "Ports"
                ]["443/tcp"][0]["HostPort"]
                for path, expected in (
                    ("/", "notoli-frontend"),
                    ("/auth/login/", "notoli-backend"),
                ):
                    self.assertEqual(
                        json.loads(wait_for_request(path, "notoli.test")[0])["service"],
                        expected,
                    )
        finally:
            for container in reversed(containers):
                subprocess.run(["docker", "rm", "-f", container], capture_output=True)
            self.docker("network", "rm", network)
            self.docker("network", "rm", notoli_network)
            subprocess.run(
                ["docker", "network", "rm", prefix + "_default"], capture_output=True
            )
