#!/usr/bin/env python3
"""Build the pinned future-aware preview without accessing any budget data."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from preview import ROOT, run


def validate_build_paths(work: Path, source: Path) -> None:
    work, source = work.resolve(), source.resolve()
    if work == source or work in source.parents or source in work.parents:
        raise ValueError('The build artifacts and reused source checkout must not overlap.')


def source_diff(source: Path, upstream: str) -> str:
    return run([
        'git', '-c', 'diff.mnemonicPrefix=false', '-c', 'core.quotePath=true',
        'diff', '--binary', '--no-color', '--no-ext-diff', '--no-renames',
        '--diff-algorithm=myers', '--src-prefix=a/', '--dst-prefix=b/', upstream,
    ], cwd=source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True, help='New directory for build artifacts; contains no budget data.')
    parser.add_argument('--source-dir', type=Path, help='Reuse an existing checkout only if its exact diff matches the tracked patch.')
    args = parser.parse_args()
    config = json.loads((ROOT / 'upstream.json').read_text())
    patch = ROOT / 'actual.patch'
    if not patch.is_file() or not patch.stat().st_size:
        raise ValueError('The tested source patch is missing.')
    fingerprint = hashlib.sha256(patch.read_bytes()).hexdigest()
    work = args.work_dir.resolve()
    source = args.source_dir.resolve() if args.source_dir else work / 'source'
    if args.source_dir:
        validate_build_paths(work, source)
    work.mkdir(parents=True, exist_ok=False)
    if not args.source_dir:
        print('Downloading the pinned upstream release.', flush=True)
        run(['git', 'clone', '--depth', '1', '--branch', config['tag'], config['repository'], str(source)])
        run(['git', 'apply', '--index', str(patch)], cwd=source)
    if run(['git', 'rev-parse', config['tag']], cwd=source) != config['commit']:
        raise ValueError('The upstream release commit does not match the pinned source.')
    if source_diff(source, config['commit']) != patch.read_text().strip():
        raise ValueError('The source contains changes outside the tracked, tested patch.')
    if run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=source):
        raise ValueError('The source checkout contains untracked files.')

    yarn = ['node', config['yarn']]
    for description, command in [
        ('Installing pinned dependencies', ['install', '--immutable']),
        ('Checking all workspace types', ['typecheck']),
        ('Building the production browser application', ['build:browser', '--skip-translations']),
    ]:
        print(description + '.', flush=True)
        run([*yarn, *command], cwd=source)
    if source_diff(source, config['commit']) != patch.read_text().strip():
        raise ValueError('The build unexpectedly changed tracked source files.')

    context = work / 'context'
    context.mkdir()
    shutil.copytree(source / 'packages/desktop-client/build', context / 'web')
    metadata = {
        'variant': 'future-aware-preview', 'version': config['version'],
        'upstreamCommit': config['commit'], 'patchSha256': fingerprint,
        'builtAtUtc': datetime.now(timezone.utc).isoformat(),
    }
    (context / 'web/future-aware-build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    image = f"actual-budget-future-aware:{config['version']}-{fingerprint[:12]}"
    print('Packaging the separate Docker image.', flush=True)
    run([
        'docker', 'build', '--pull=false', '--tag', image,
        '--build-arg', 'ACTUAL_BASE_IMAGE=' + config['base_image'],
        '--file', str(ROOT / 'Dockerfile'), str(context),
    ])
    (work / 'build-result.json').write_text(json.dumps({'image': image, **metadata}, indent=2) + '\n')
    print(image)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f'Build stopped: {error}') from error
