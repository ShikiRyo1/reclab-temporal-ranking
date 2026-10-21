"""Download the official, checksum-pinned MovieLens 1M research dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

URL = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
EXPECTED_SHA256 = "a6898adb50b9ca05aa231689da44c217cb524e7ebd39d264c56e2832f2c54e20"


def prepare(destination: Path) -> dict:
    """Keep data separate from Git and reject archive drift or path traversal."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "ml-1m.zip"
    downloaded = False
    if not archive.exists():
        partial = archive.with_suffix(".zip.part")
        with urllib.request.urlopen(URL, timeout=60) as response, partial.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        partial.replace(archive)
        downloaded = True
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Dataset checksum differs; do not silently change the experiment.")
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Archive member escapes the chosen data directory.")
        if not (destination / "ml-1m/ratings.dat").exists():
            zipped.extractall(destination)
        extracted_hashes = {}
        for member in zipped.infolist():
            if member.is_dir():
                continue
            source_hash = hashlib.sha256(zipped.read(member)).hexdigest()
            target = destination / member.filename
            if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != source_hash:
                raise ValueError(f"Extracted source differs from pinned archive: {member.filename}")
            extracted_hashes[member.filename] = source_hash
    receipt = {
        "url": URL, "archive": str(archive), "sha256": digest, "bytes": archive.stat().st_size,
        "downloaded_this_run": downloaded, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "license_file": str(destination / "ml-1m/README"),
        "extracted_file_sha256": extracted_hashes,
        "redistribution": "Do not redistribute source data without GroupLens permission.",
    }
    (destination / "ml-1m_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().data_dir), indent=2))
