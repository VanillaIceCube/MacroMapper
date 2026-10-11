#!/usr/bin/env python3
"""Create an SQLite-consistent backup and verify it before accepting it."""

import argparse
import os
import sqlite3
from pathlib import Path


def backup(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Source must be an existing database file")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Refuse overwriting an existing backup, including the source database.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(destination) as snapshot:
                original.backup(snapshot)
                if snapshot.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Backup failed SQLite integrity check")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    backup(args.source, args.destination)
