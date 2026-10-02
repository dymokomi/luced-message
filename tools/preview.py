#!/usr/bin/env python3
"""Capture a real Metal frame of the window, after its sources synced, as a PNG.

    tools/preview.py --home DIR [--position N] [--output build/preview.png]

DIR holds accounts.toml (and the store, which the run fills). Uses luce-gpu's
test observer to read the drawable back; no screen access is needed."""
from pathlib import Path
import argparse, os, shutil, struct, subprocess, tempfile, zlib

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--home", type=Path, required=True)
parser.add_argument("--position", type=int, default=0)
parser.add_argument("--output", type=Path, default=ROOT / "build/preview.png")
arguments = parser.parse_args()


def chunk(tag, payload):
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff)


with tempfile.TemporaryDirectory(prefix="luced-message-preview-") as temporary:
    project = Path(temporary)
    shutil.copytree(ROOT / "src", project / "src")
    shutil.copy2(ROOT / "tools/preview.luc", project / "src/main.luc")
    native = (ROOT.parent / "luce-gpu/tests/programs/gpu/native.lucb").read_text()
    (project / "src/probe.lucb").write_text(native + "\n" + (ROOT / "tools/readback.lucb").read_text())
    manifest = (ROOT / "package.prisma").read_text()
    for name in [line.split('"')[1] for line in manifest.splitlines() if line.strip().startswith("def dependency")]:
        manifest = manifest.replace(f'"../{name}"', f'"{ROOT.parent / name}"')
    (project / "package.prisma").write_text(manifest)
    binary = project / "preview"
    environment = dict(os.environ, LUCE_CACHE=str(ROOT / "build/cache"))
    subprocess.run([os.environ.get("LUCE", "luce"), "build", str(project / "src/main.luc"), "--native", "-o", str(binary)], check=True, env=environment, timeout=600)
    ppm = project / "preview.ppm"
    subprocess.run([str(binary), str(ppm), str(arguments.home.resolve()), str(arguments.position)], check=True, timeout=120)
    header, dimensions, maximum, pixels = ppm.read_bytes().split(b"\n", 3)
    width, height = map(int, dimensions.split())
    rows = b"".join(b"\0" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(png)
    print(f"{arguments.output} ({width} × {height})")
