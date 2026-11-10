#!/usr/bin/env python3
"""Optional serialized update cycle for a dedicated demo deployment."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / '.deploy'
ENV = os.environ.copy()
ENV['PATH'] = '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:' + ENV.get('PATH', '')
ENV['GIT_TERMINAL_PROMPT'] = '0'
ENV['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes -o ConnectTimeout=15'


def run(args, cwd=ROOT, env=None, capture=False):
    return subprocess.run(args, cwd=str(cwd), env=env or ENV, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None,
                          timeout=1200).stdout


def compose(release, sha, *args, capture=False):
    env = ENV.copy()
    env.update(SALON_IMAGE='salon-scheduler-demo:' + sha,
               WEBSITE_IMAGE='salon-scheduler-demo-website:' + sha, APP_REVISION=sha,
               COMPOSE_PROFILES='website' if (release / 'Website' / 'Dockerfile').exists() else '')
    return run(['docker', 'compose', '--project-name', 'salon-scheduler-demo',
                '--project-directory', str(ROOT), '--env-file', str(ROOT / '.env'),
                '-f', str(release / 'compose.yaml'), *args], env=env, capture=capture)


def deploy():
    if not (ROOT / '.env').exists():
        raise RuntimeError('Copy .env.example to .env before deployment.')
    run(['docker', 'info'], capture=True)
    branch = ENV.get('UPDATE_BRANCH', 'main')
    run(['git', 'fetch', '--no-tags', 'origin', branch])
    sha = run(['git', 'rev-parse', 'FETCH_HEAD'], capture=True).strip()
    state_path = DEPLOY / 'current.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    release = DEPLOY / 'releases' / sha
    if previous and previous['sha'] == sha:
        # Reconcile a stopped container without rebuilding an unchanged release.
        compose(release, sha, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '120')
        return
    print('Preparing release ' + sha, flush=True)
    if not release.exists():
        release.parent.mkdir(parents=True, exist_ok=True)
        # Git worktree gives an immutable, exact commit, preserving the main checkout.
        run(['git', 'worktree', 'add', '--detach', str(release), sha])
    image = 'salon-scheduler-demo:' + sha
    run(['docker', 'build', '-t', image, str(release)])
    run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
         '--mount', 'type=bind,source=' + str(release / 'tests') + ',target=/app/tests,readonly',
         image, 'python', '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    # Build the public website before replacing either running service.
    if (release / 'Website' / 'Dockerfile').exists():
        run(['docker', 'build', '-t', 'salon-scheduler-demo-website:' + sha, str(release / 'Website')])
    # Back up the live SQLite database before replacing an existing release.
    if previous:
        old = Path(previous['release'])
        backup_code = "import sqlite3; a=sqlite3.connect('/app/data/salon.sqlite3'); b=sqlite3.connect('/app/data/pre-update.sqlite3'); a.backup(b); b.close(); a.close()"
        compose(old, previous['sha'], 'exec', '-T', 'salon', 'python', '-c', backup_code)
        backups = DEPLOY / 'backups'
        backups.mkdir(exist_ok=True)
        compose(old, previous['sha'], 'cp', 'salon:/app/data/pre-update.sqlite3', str(backups / (previous['sha'] + '.sqlite3')))
    try:
        compose(release, sha, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '120')
    except subprocess.CalledProcessError:
        if previous:
            print('New release unhealthy; restoring previous container image.', flush=True)
            # Older releases had no website service; remove a failed first rollout.
            if (release / 'Website').exists() and not (Path(previous['release']) / 'Website').exists():
                compose(release, sha, 'rm', '--stop', '--force', 'website')
            compose(Path(previous['release']), previous['sha'], 'up', '-d', '--no-build', '--wait', '--wait-timeout', '120')
        raise
    pending = DEPLOY / 'current.json.tmp'
    pending.write_text(json.dumps({'sha': sha, 'release': str(release)}))
    pending.replace(state_path)
    print('Healthy release running: ' + sha, flush=True)


if __name__ == '__main__':
    DEPLOY.mkdir(exist_ok=True)
    with (DEPLOY / 'update.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(0)
        try:
            deploy()
        except (subprocess.SubprocessError, RuntimeError, OSError) as exc:
            print('Update failed; will retry on next scheduled check: ' + str(exc), file=sys.stderr, flush=True)
            sys.exit(1)
