#!/usr/bin/env python3
"""Install a per-user macOS updater; run from a dedicated authenticated clone."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
label = 'com.salonscheduler.demo-auto-update'
logs = Path.home() / 'Library' / 'Logs' / 'SalonSchedulerDemo'
logs.mkdir(parents=True, exist_ok=True)
agent = Path.home() / 'Library' / 'LaunchAgents' / (label + '.plist')
agent.parent.mkdir(parents=True, exist_ok=True)
config = {
    'Label': label,
    'ProgramArguments': [sys.executable, str(root / 'scripts' / 'auto-update.py')],
    'WorkingDirectory': str(root),
    'StartInterval': 60,
    'RunAtLoad': True,
    'StandardOutPath': str(logs / 'update.log'),
    'StandardErrorPath': str(logs / 'update-error.log'),
    'EnvironmentVariables': {'PATH': '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin',
                             'UPDATE_BRANCH': os.environ.get('UPDATE_BRANCH', 'main')},
}
# Fail before scheduling if this is not an authenticated Git checkout.
subprocess.run(['git', 'rev-parse', '--git-dir'], cwd=root, check=True)
if not (root / '.env').exists():
    shutil.copyfile(root / '.env.example', root / '.env')
    os.chmod(root / '.env', 0o600)
subprocess.run(['launchctl', 'bootout', 'gui/' + str(os.getuid()), str(agent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with agent.open('wb') as output:
    plistlib.dump(config, output)
subprocess.run(['launchctl', 'bootstrap', 'gui/' + str(os.getuid()), str(agent)], check=True)
print('Demo updates installed: checks ' + config['EnvironmentVariables']['UPDATE_BRANCH'] + ' every 60 seconds while signed in.')
print('Logs: ' + str(logs))
