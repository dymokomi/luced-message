#!/usr/bin/env python3
"""Run luced-message's headless tests: the application's modules with tests/main.luc
as the entry, in a temporary package, without a window."""
import argparse, os, re, json, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
package_version = re.search(r'^    str version = "([^"]+)"', (ROOT / 'package.prisma').read_text(), re.M).group(1)
app_version = re.search(r'pub let version: str = "([^"]+)"', (ROOT / 'src/app.luc').read_text()).group(1)
if app_version != package_version:
    raise SystemExit(f'src/app.luc says {app_version}; package.prisma says {package_version}')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', type=Path, default=ROOT.parent / 'luce-base/build/luce-base')
parser.add_argument('--luce', type=Path, default=Path(shutil.which('luce') or ROOT.parent / 'luce/build/luce'))
arguments = parser.parse_args()
(ROOT / 'build').mkdir(exist_ok=True)
environment = dict(os.environ, LUCE_BASE=str(arguments.base.resolve()), LUCE_CACHE=str(ROOT / 'build/cache'))
with tempfile.TemporaryDirectory(prefix='luced-message-tests-') as temp:
    project = Path(temp) / 'application'
    shutil.copytree(ROOT / 'src', project / 'src')
    for module in (ROOT / 'tests').glob('*.luc'):
        shutil.copy2(module, project / 'src' / module.name)
    manifest = (ROOT / 'package.prisma').read_text()
    for name in re.findall(r'def dependency "([^"]+)"', manifest):
        manifest = manifest.replace(f'"../{name}"', json.dumps(str(ROOT.parent / name)))
    manifest = manifest.replace('def package "luced-message"', 'def package "luced-message-tests"').replace('str kind = "application"', 'str kind = "tool"')
    (project / 'package.prisma').write_text(manifest)
    binary = Path(temp) / 'tests'
    subprocess.run([str(arguments.luce), 'build', str(project / 'src/main.luc'), '--native', '-o', str(binary)], env=environment, check=True, timeout=600)
    subprocess.run([str(binary), str(Path(temp) / 'scratch')], env=environment, check=True, timeout=120)
