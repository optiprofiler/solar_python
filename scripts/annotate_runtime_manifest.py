"""Add wrapper-distribution license data to the synced SOLAR manifest."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "runtime" / "solar" / "manifest.json"
LICENSE_EXPRESSION = (
    "BSD-3-Clause AND LGPL-2.1-only AND LGPL-3.0-or-later"
)


def main():
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    policy = manifest.setdefault("policy", {})
    policy.pop("vendor_source", None)
    policy["vendor_complete_upstream_checkout"] = False

    manifest["distribution"] = {
        "license_expression": LICENSE_EXPRESSION,
        "contains_upstream_source_subset": True,
        "adapter": {
            "license": "BSD-3-Clause",
            "license_file": "LICENSE",
        },
        "upstream_repository_files": {
            "license": "LGPL-2.1-only",
            "paths": [
                "runtime/solar/src/makefile",
                "runtime/solar/README.upstream.md",
            ],
            "license_file": "runtime/solar/LICENSE",
        },
        "upstream_license_text": {
            "path": "runtime/solar/LICENSE",
            "identifier": "LGPL-2.1-only",
            "role": "verbatim upstream repository license and conservative basis for unheaded upstream files",
        },
        "upstream_source_headers": {
            "license": "LGPL-3.0-or-later",
            "patterns": [
                "runtime/solar/src/*.cpp",
                "runtime/solar/src/*.hpp",
            ],
            "license_files": [
                "licenses/GPL-3.0.txt",
                "licenses/LGPL-3.0.txt",
            ],
        },
        "notice_file": "THIRD_PARTY_NOTICES.md",
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
