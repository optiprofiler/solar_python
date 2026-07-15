"""Check license metadata and contents of built distribution archives."""

from email.parser import BytesParser
from email.policy import default
from hashlib import sha256
import json
from pathlib import Path
import tarfile
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE_PREFIX = "optiprofiler_solar/"
LICENSE_EXPRESSION = (
    "BSD-3-Clause AND LGPL-2.1-only AND LGPL-3.0-or-later"
)
GPL3_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"
LGPL3_SHA256 = "e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118"
UPSTREAM_LICENSE_SHA256 = (
    "20c17d8b8c48a600800dfd14f95d5cb9ff47066a9641ddeab48dc54aec96e331"
)
UPSTREAM_REPOSITORY_FILES = {
    "runtime/solar/src/makefile",
    "runtime/solar/README.upstream.md",
}


def _find_one(pattern):
    matches = list(DIST.glob(pattern))
    if len(matches) != 1:
        raise AssertionError(f"Expected one {pattern!r} archive, found {matches}")
    return matches[0]


def _require_suffixes(names, suffixes):
    for suffix in suffixes:
        if not any(name.endswith(suffix) for name in names):
            raise AssertionError(f"Distribution is missing {suffix}")


def main():
    wheel = _find_one("*.whl")
    sdist = _find_one("*.tar.gz")

    with ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        metadata_name = next(
            name for name in wheel_names if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser(policy=default).parsebytes(
            archive.read(metadata_name)
        )
        manifest = json.loads(
            archive.read(
                f"{PACKAGE_PREFIX}runtime/solar/manifest.json"
            ).decode("utf-8")
        )
        source_names = [
            name
            for name in wheel_names
            if name.startswith(f"{PACKAGE_PREFIX}runtime/solar/src/")
            and name.endswith((".cpp", ".hpp"))
        ]
        for name in source_names:
            header = archive.read(name).decode("utf-8", errors="replace")[:1800]
            if "either version 3 of the License" not in header:
                raise AssertionError(f"Missing LGPL-3-or-later header in {name}")
        gpl_bytes = archive.read(f"{PACKAGE_PREFIX}licenses/GPL-3.0.txt")
        lgpl_bytes = archive.read(f"{PACKAGE_PREFIX}licenses/LGPL-3.0.txt")
        upstream_license_bytes = archive.read(
            f"{PACKAGE_PREFIX}runtime/solar/LICENSE"
        )

    _require_suffixes(
        wheel_names,
        [
            f"{PACKAGE_PREFIX}LICENSE",
            f"{PACKAGE_PREFIX}THIRD_PARTY_NOTICES.md",
            f"{PACKAGE_PREFIX}licenses/GPL-3.0.txt",
            f"{PACKAGE_PREFIX}licenses/LGPL-3.0.txt",
            f"{PACKAGE_PREFIX}runtime/solar/LICENSE",
            f"{PACKAGE_PREFIX}runtime/solar/src/makefile",
            f"{PACKAGE_PREFIX}runtime/solar/README.upstream.md",
        ],
    )
    if metadata["License"] != LICENSE_EXPRESSION:
        raise AssertionError(
            f"Unexpected wheel license metadata: {metadata['License']!r}"
        )
    if metadata.get("License-Expression") is not None:
        raise AssertionError("Legacy Python 3.8 build must not emit mixed metadata")
    if len(source_names) != 49:
        raise AssertionError(f"Expected 49 licensed C++ files, found {len(source_names)}")
    if manifest.get("distribution", {}).get("license_expression") != LICENSE_EXPRESSION:
        raise AssertionError("Runtime manifest has stale distribution license data")
    distribution = manifest["distribution"]
    repository_files = distribution.get("upstream_repository_files", {})
    if set(repository_files.get("paths", [])) != UPSTREAM_REPOSITORY_FILES:
        raise AssertionError("Manifest does not map every unheaded upstream file")
    if repository_files.get("license") != "LGPL-2.1-only":
        raise AssertionError("Manifest has the wrong unheaded-file license")
    source_headers = distribution.get("upstream_source_headers", {})
    if source_headers.get("license") != "LGPL-3.0-or-later":
        raise AssertionError("Manifest has the wrong C++ source license")
    if set(source_headers.get("patterns", [])) != {
        "runtime/solar/src/*.cpp",
        "runtime/solar/src/*.hpp",
    }:
        raise AssertionError("Manifest does not map all C++ source patterns")
    license_text = distribution.get("upstream_license_text", {})
    if license_text.get("path") != "runtime/solar/LICENSE":
        raise AssertionError("Manifest does not record the upstream license text")
    if license_text.get("identifier") != "LGPL-2.1-only":
        raise AssertionError("Manifest has the wrong upstream license identifier")
    if sha256(gpl_bytes).hexdigest() != GPL3_SHA256:
        raise AssertionError("Packaged GPLv3 text differs from the official text")
    if sha256(lgpl_bytes).hexdigest() != LGPL3_SHA256:
        raise AssertionError("Packaged LGPLv3 text differs from the official text")
    if sha256(upstream_license_bytes).hexdigest() != UPSTREAM_LICENSE_SHA256:
        raise AssertionError("Packaged upstream LGPLv2.1 text differs from the pinned commit")

    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
    _require_suffixes(
        sdist_names,
        [
            "/LICENSE",
            "/THIRD_PARTY_NOTICES.md",
            "/licenses/GPL-3.0.txt",
            "/licenses/LGPL-3.0.txt",
            "/runtime/solar/LICENSE",
            "/runtime/solar/manifest.json",
            "/runtime/solar/src/makefile",
        ],
    )


if __name__ == "__main__":
    main()
