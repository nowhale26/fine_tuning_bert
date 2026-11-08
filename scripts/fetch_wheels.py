"""Fetch CPython 3.8 Windows wheels with curl for an offline pip install.

Uses pip's vendored packaging only to select compatible releases and wheel tags.
All downloads and SHA256 checks are recorded under downloads/.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import cpython_tags, compatible_tags
from pip._vendor.packaging.utils import parse_wheel_filename
from pip._vendor.packaging.version import Version, InvalidVersion

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / "downloads" / "wheels"
METADATA = ROOT / "downloads" / "pypi"
for directory in (WHEELS, METADATA):
    directory.mkdir(parents=True, exist_ok=True)
TAGS = set(cpython_tags((3, 8), platforms=["win_amd64"]))
TAGS.update(compatible_tags((3, 8), interpreter="cp38", platforms=["win_amd64"]))


class DownloadRequested(Exception):
    pass


def curl(url, output):
    if "--emit-downloads" in sys.argv:
        print("DOWNLOAD_REQUEST " + json.dumps({"url": url, "output": str(output)}), flush=True)
        raise DownloadRequested()
    subprocess.run(["curl.exe", "-L", "--fail", "--silent", "--show-error",
                    "--retry", "3", "--retry-connrefused", "--connect-timeout", "30",
                    "-o", str(output), url], check=True)


def metadata(name, version=None):
    output = METADATA / (name + ("-" + version if version else "") + ".json")
    if not output.exists():
        curl("https://pypi.org/pypi/" + name + ("/" + version if version else "") + "/json", output)
    return json.loads(output.read_text(encoding="utf-8"))


def compatible(file):
    if file["packagetype"] != "bdist_wheel" or file.get("yanked"):
        return False
    if file.get("requires_python") and not SpecifierSet(file["requires_python"]).contains("3.8.10"):
        return False
    try:
        return bool(parse_wheel_filename(file["filename"])[3] & TAGS)
    except Exception:
        return False


def fetch(requirement):
    req = Requirement(requirement)
    project = metadata(req.name)
    versions = []
    for number, files in project["releases"].items():
        try:
            version = Version(number)
        except InvalidVersion:
            continue
        if version.is_prerelease or version.is_devrelease or not req.specifier.contains(version):
            continue
        matches = [f for f in files if compatible(f)]
        # pathtools is a small pure-Python dependency of the historical W&B SDK.
        if not matches and req.name.lower() == "pathtools":
            matches = [f for f in files if f["packagetype"] == "sdist" and not f.get("yanked")]
        if matches:
            versions.append((version, matches))
    if not versions:
        raise RuntimeError("No CPython 3.8 Windows wheel for " + requirement)
    version, matches = max(versions, key=lambda pair: pair[0])
    file = matches[0]
    target = WHEELS / file["filename"]
    if not target.exists():
        print("FETCH " + req.name + " " + str(version) + " " + file["filename"], flush=True)
        curl(file["url"], target)
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != file["digests"]["sha256"]:
        raise RuntimeError("SHA256 mismatch: " + str(target))
    return target


def install(arguments, bootstrap=False):
    python = ROOT / ".runtime" / "python38" / "python.exe"
    prefix = [str(python), str(ROOT / "downloads" / "get-pip.py")] if bootstrap else [str(python), "-m", "pip", "install"]
    command = prefix + ["--no-index", "--no-cache-dir", "--find-links", str(WHEELS), "--find-links", str(ROOT / "downloads"), "--no-warn-script-location"] + arguments
    attempted = set()
    for _ in range(100):
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        (ROOT / "results" / "pilot" / "offline-install.log").open("a", encoding="utf-8").write(process.stdout + "\n")
        if process.returncode == 0:
            print(process.stdout[-2000:], flush=True)
            return
        missing = re.search(r"Could not find a version that satisfies the requirement (.+?) \(from versions:", process.stdout)
        if not missing:
            raise RuntimeError(process.stdout[-6000:])
        requirement = re.split(r" \(from ", missing.group(1), maxsplit=1)[0]
        if requirement in attempted:
            raise RuntimeError("Resolution stalled: " + requirement + "\n" + process.stdout[-4000:])
        attempted.add(requirement)
        fetch(requirement)
    raise RuntimeError("Too many resolution attempts")


if __name__ == "__main__":
    try:
        if sys.argv[1] == "bootstrap":
            install(["pip==24.3.1", "setuptools==68.2.2", "wheel==0.45.1"], bootstrap=True)
        elif sys.argv[1] == "requirements":
            install(["-r", str(ROOT / "environment" / "requirements-pilot.txt")])
        elif sys.argv[1] == "torch":
            install(["torch==1.13.1+cu117"])
    except DownloadRequested:
        sys.exit(3)
