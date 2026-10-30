"""Stage an app-owned disabled-policy rollback tool before first MCP activation.

This prepares public policy/code only. It never runs a release, edits a private
bundle/recovery set, copies credentials, or changes the common release engine.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


def prepare(target, source_revision):
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ValueError("An exact reviewed source revision is required")
    config = json.loads((SOURCE / "app.json").read_text(encoding="utf-8"))
    delta = json.loads(
        (SOURCE / "mcp-disabled-policy.json").read_text(encoding="utf-8")
    )
    if config["app"] != "macromapper" or config["contract_version"] != 1:
        raise ValueError("MacroMapper release policy required")
    config["environment"]["fixed"].update(delta["environment_fixed_patch"])
    for key in delta["environment_fixed_remove"]:
        config["environment"]["fixed"].pop(key, None)
    config["environment"]["required"] = [
        key
        for key in config["environment"]["required"]
        if key not in delta["environment_required_remove"]
    ]
    config["environment"]["defaults"].update(delta["environment_defaults_patch"])
    config["readiness"]["public"] = [
        rule
        for rule in config["readiness"]["public"]
        if rule["path"] not in delta["readiness_public_remove"]
    ]
    target.mkdir(
        mode=0o700
    )  # Fresh destination only; never modify an immutable bundle.
    payload = {
        "release.py": (SOURCE / "release.py").read_bytes(),
        "app.json": (json.dumps(config, indent=2) + "\n").encode(),
    }
    manifest = {
        "source_revision": source_revision,
        "shared_source": json.loads(
            (SOURCE.parent / "shared-source.json").read_text(encoding="utf-8")
        ),
        "sha256": {
            name: hashlib.sha256(data).hexdigest() for name, data in payload.items()
        },
    }
    for name, data in payload.items():
        path = target / name
        path.write_bytes(data)
        path.chmod(0o600)
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (target / "manifest.json").chmod(0o600)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    arguments = parser.parse_args()
    prepare(arguments.target, arguments.source_revision)
    print("Prepared disabled MCP rollback tool; verify and stage before activation.")
