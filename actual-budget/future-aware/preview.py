#!/usr/bin/env python3
"""Build an isolated Actual Budget preview from a private data snapshot."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
STATE_KIND = 'actual-future-aware-preview-v1'


def run(arguments: list[str], *, env: dict | None = None, cwd: Path | None = None) -> str:
    result = subprocess.run(arguments, env=env, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def validate_paths(source: Path, destination: Path) -> None:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('The preview destination and source data must not overlap.')
    if not source.is_dir():
        raise ValueError('The source data directory does not exist.')
    if destination.exists():
        raise FileExistsError('The preview destination already exists; use resume or choose a new directory.')


def validate_ports(actual_port: int, tweaks_port: int) -> None:
    ports = actual_port, tweaks_port
    if any(type(port) is not int or port < 1 or port > 65535 or port in {5006, 3005} for port in ports):
        raise ValueError('Use valid preview ports other than the live ports 5006 and 3005.')
    if actual_port == tweaks_port:
        raise ValueError('The two preview ports must be different.')


def project_name(destination: Path) -> str:
    return 'actual-future-' + hashlib.sha256(os.fsencode(destination.resolve())).hexdigest()[:12]


def inventory(source: Path) -> dict:
    files = {}
    for item in sorted(source.rglob('*')):
        if item.is_symlink():
            raise ValueError('The source data contains a symlink; refusing an ambiguous snapshot.')
        if item.is_file() and not item.name.endswith('-shm'):
            stat = item.stat()
            files[str(item.relative_to(source))] = stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    return files


def copy_snapshot(source: Path, destination: Path) -> int:
    validate_paths(source, destination)
    for attempt in range(3):
        before = inventory(source)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='.actual-preview-copy-', dir=destination.parent) as temporary:
            copied = Path(temporary) / 'data'
            copied.mkdir(mode=0o700)
            count = 0
            for relative in before:
                if relative.endswith('-wal'):
                    continue
                original, target = source / relative, copied / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with original.open('rb') as stream:
                    sqlite_file = stream.read(16) == b'SQLite format 3\x00'
                if sqlite_file:
                    deadline = time.monotonic() + 30

                    def progress(_status, _remaining, _total):
                        if time.monotonic() > deadline:
                            raise TimeoutError('The database remained busy while copying.')

                    with closing(sqlite3.connect(original.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
                        with closing(sqlite3.connect(target)) as backup:
                            connection.backup(backup, pages=256, progress=progress)
                            if backup.execute('PRAGMA quick_check').fetchone() != ('ok',):
                                raise RuntimeError('A copied database failed its integrity check.')
                else:
                    shutil.copyfile(original, target)
                target.chmod(0o600)
                count += 1
            if before == inventory(source):
                copied.rename(destination)
                destination.chmod(0o700)
                return count
        if attempt < 2:
            time.sleep(0.2)
    raise RuntimeError('The source changed during every copy attempt. Close budget tabs and retry.')


def load_state(destination: Path) -> dict:
    destination = destination.resolve()
    state = json.loads((destination / 'state.json').read_text())
    if state.get('kind') != STATE_KIND or state.get('project') != project_name(destination):
        raise ValueError('This directory does not identify an owned future-aware preview.')
    if Path(state.get('data_dir', '')).resolve() != destination / 'data':
        raise ValueError('The preview data directory does not match its private destination.')
    if Path(state.get('source_data', '')).resolve() == destination / 'data':
        raise ValueError('The preview cannot use the source data directory directly.')
    validate_ports(state['actual_port'], state['tweaks_port'])
    return state


def compose(state: dict, *arguments: str) -> str:
    env = os.environ.copy()
    env.update({
        'ACTUAL_PREVIEW_IMAGE': state['image'],
        'ACTUAL_PREVIEW_DATA_DIR': state['data_dir'],
        'ACTUAL_PREVIEW_PORT': str(state['actual_port']),
        'ACTUAL_PREVIEW_TWEAKS_PORT': str(state['tweaks_port']),
    })
    return run(['docker', 'compose', '--project-name', state['project'], '--file', str(ROOT / 'compose.yaml'), *arguments], env=env)


def validate_resume_data(state: dict) -> None:
    data = Path(state['data_dir'])
    if not all((data / directory).is_dir() for directory in ['server-files', 'user-files']):
        raise ValueError('The private preview data copy is missing. Start a new snapshot instead.')


def preflight(state: dict) -> None:
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:/@-]+', state['image']):
        raise ValueError('Invalid preview image reference.')
    label = run(['docker', 'image', 'inspect', '--format', '{{index .Config.Labels "io.pratik.actual.future-aware"}}', state['image']])
    if label != 'true':
        raise ValueError('Build the labeled future-aware image before starting this preview.')
    existing = run(['docker', 'ps', '-a', '--filter', 'label=com.docker.compose.project=' + state['project'], '--format', '{{.ID}}'])
    if existing:
        raise ValueError('This preview project already has containers; use status or stop first.')
    for port in (state['actual_port'], state['tweaks_port']):
        with socket.socket() as listener:
            # Recently closed preview connections may still be in TIME_WAIT.
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(('127.0.0.1', port))
                listener.listen()
            except OSError as error:
                raise ValueError(f'Preview port {port} is already in use.') from error


def start(args) -> None:
    source, destination = args.source_data.resolve(), args.destination.resolve()
    validate_paths(source, destination)
    validate_ports(args.port, args.tweaks_port)
    if not all((source / directory).is_dir() for directory in ['server-files', 'user-files']):
        raise ValueError('Use the Actual data folder containing server-files and user-files.')
    state = {
        'kind': STATE_KIND, 'project': project_name(destination),
        'source_data': str(source), 'data_dir': str(destination / 'data'),
        'image': args.image, 'actual_port': args.port, 'tweaks_port': args.tweaks_port,
    }
    preflight(state)
    destination.mkdir(mode=0o700, parents=True)
    copied = copy_snapshot(source, destination / 'data')
    (destination / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    (destination / 'state.json').chmod(0o600)
    print(f'Created a private snapshot of {copied} files. Starting the separate preview.', flush=True)
    print(compose(state, 'up', '-d', '--wait', '--wait-timeout', '90'))
    print(f"Preview: http://localhost:{state['tweaks_port']} (direct: http://localhost:{state['actual_port']})")


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    begin = commands.add_parser('start')
    begin.add_argument('--source-data', type=Path, required=True)
    begin.add_argument('--destination', type=Path, required=True)
    begin.add_argument('--image', required=True)
    begin.add_argument('--port', type=int, default=15006)
    begin.add_argument('--tweaks-port', type=int, default=13005)
    for command in ['status', 'stop', 'resume']:
        commands.add_parser(command).add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'start':
        start(args)
    else:
        state = load_state(args.destination)
        if args.command == 'stop':
            print(compose(state, 'down'))
            print('Stopped only the preview. Its private data copy is retained.')
        elif args.command == 'resume':
            validate_resume_data(state)
            preflight(state)
            print(compose(state, 'up', '-d', '--wait', '--wait-timeout', '90'))
        else:
            print(compose(state, 'ps'))
            print(f"Preview: http://localhost:{state['tweaks_port']}")


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(f'Preview stopped: {error}') from error
