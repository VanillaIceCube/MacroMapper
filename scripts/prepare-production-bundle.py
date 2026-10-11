"""Stage the existing production images/configuration without logging secrets."""

import os
import re
import shutil
import sys
from pathlib import Path

DOMAIN = "macromapper.judeandrewalaba.com"
ORIGIN = f"https://{DOMAIN}"
DEFAULTS = {
    "DJANGO_DEBUG": "0",
    "DJANGO_SQLITE_PATH": "/backend/db.sqlite3",
    "DJANGO_FORCE_SCRIPT_NAME": "",
    "DJANGO_EMAIL_HOST": "smtp.resend.com",
    "DJANGO_EMAIL_PORT": "587",
    "DJANGO_EMAIL_USE_TLS": "1",
    "DJANGO_EMAIL_HOST_USER": "resend",
    "DJANGO_EMAIL_TIMEOUT": "10",
    "OPENAI_MEAL_ESTIMATION_MODEL": "gpt-5.6-luna",
    "OPENAI_MEAL_ESTIMATION_TIMEOUT": "45",
}
REQUIRED = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_FRONTEND_BASE_URL",
    "DJANGO_EMAIL_BACKEND",
    "DJANGO_EMAIL_HOST_KEY",
    "DJANGO_DEFAULT_FROM_EMAIL",
    "MACROMAPPER_OPENAI_API_KEY",
)


def production_values(environment):
    values = {key: environment.get(key) or value for key, value in DEFAULTS.items()}
    values.update({key: environment.get(key, "") for key in REQUIRED})
    missing = [key for key in REQUIRED if not values[key].strip()]
    if missing:
        raise ValueError("Missing production settings: " + ", ".join(missing))
    for key, value in values.items():
        if any(character in value for character in "\r\n\x00"):
            raise ValueError(f"{key} must be a single-line environment value.")
    for key, expected in {
        "DJANGO_DEBUG": "0",
        "DJANGO_SQLITE_PATH": "/backend/db.sqlite3",
        "DJANGO_FORCE_SCRIPT_NAME": "",
        "DJANGO_FRONTEND_BASE_URL": ORIGIN,
    }.items():
        if values[key] != expected:
            raise ValueError(f"{key} must match the documented production routing.")
    for key, expected in {
        "DJANGO_ALLOWED_HOSTS": DOMAIN,
        "DJANGO_CORS_ALLOWED_ORIGINS": ORIGIN,
        "DJANGO_CSRF_TRUSTED_ORIGINS": ORIGIN,
    }.items():
        if [part.strip() for part in values[key].split(",")] != [expected]:
            raise ValueError(f"{key} must name only the production application.")
    if environment.get("VITE_API_BASE_URL", ""):
        raise ValueError("VITE_API_BASE_URL must be empty for same-origin production.")
    if values["DJANGO_EMAIL_BACKEND"] not in (
        "authentication.email_backends.ResendApiEmailBackend",
        "django.core.mail.backends.smtp.EmailBackend",
    ):
        raise ValueError("Configure Resend API or SMTP delivery for password resets.")
    return values


def prepare_bundle(target, environment, revision, owner, root):
    values = production_values(environment)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("The release revision must be a full Git commit SHA.")
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Invalid GHCR owner.")
    target.mkdir(mode=0o700)
    for source, name in (
        ("deploy/docker-compose.yml", "docker-compose.yml"),
        ("deploy/docker-compose.shared.yml", "docker-compose.shared.yml"),
        ("deploy/nginx-shared.conf", "nginx-shared.conf"),
        ("scripts/deploy-production.sh", "deploy-production.sh"),
    ):
        shutil.copyfile(root / source, target / name)
    backend_env = target / ".backend.env.next"
    with backend_env.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    backend_env.chmod(0o600)
    release_env = target / ".env.next"
    release_env.write_text(
        f"MACROMAPPER_BACKEND_IMAGE=ghcr.io/{owner.lower()}/macromapper-backend:sha-{revision}\n"
        f"MACROMAPPER_FRONTEND_IMAGE=ghcr.io/{owner.lower()}/macromapper-frontend:sha-{revision}\n",
        encoding="utf-8",
    )
    release_env.chmod(0o600)


if __name__ == "__main__":
    try:
        prepare_bundle(
            Path(sys.argv[1]),
            os.environ,
            os.environ["GITHUB_SHA"],
            os.environ["GITHUB_REPOSITORY_OWNER"],
            Path(__file__).resolve().parents[1],
        )
    except (ValueError, KeyError) as error:
        sys.exit(str(error))
