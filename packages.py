"""Read-only Debian package version baselines for explicitly named packages."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

PACKAGE = re.compile(r'[a-z0-9][a-z0-9+.-]{0,199}(?::[a-z0-9][a-z0-9-]{0,31})?')


def read_package(name):
    binary = shutil.which('dpkg-query')
    if not binary: raise RuntimeError('dpkg-query is unavailable')
    command = [binary, '-W', '-f=${db:Status-Status}\\t${Version}\\n', '--', name]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env={'PATH':os.defpath,'LANG':'C.UTF-8'}, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Package state could not be read') from exc
    if result.returncode or len(result.stdout) > 8192: raise RuntimeError('Package state could not be read')
    try: fields = result.stdout.decode('utf-8').strip().split('\t')
    except UnicodeError as exc: raise RuntimeError('Package state was not valid text') from exc
    if len(fields) != 2 or not fields[0] or not fields[1]: raise RuntimeError('Package state is incomplete')
    return {'status':fields[0], 'version':fields[1]}


class Packages:
    def __init__(self, root): self.root = Path(root)

    def path(self, baseline_id):
        if not isinstance(baseline_id,str) or len(baseline_id)!=32 or any(c not in '0123456789abcdef' for c in baseline_id):
            raise ValueError('Invalid package baseline ID')
        path = self.root/(baseline_id+'.packages.json')
        if path.is_symlink(): raise ValueError('Invalid package baseline')
        return path

    def baseline_packages(self, packages):
        if not isinstance(packages,list) or not 1 <= len(packages) <= 20 or any(not isinstance(x,str) or not PACKAGE.fullmatch(x) for x in packages) or len(set(packages)) != len(packages):
            raise ValueError('Choose 1–20 distinct explicit Debian package names')
        states = {name:read_package(name) for name in packages}
        if any(state['status'] != 'installed' for state in states.values()):
            raise ValueError('Every baseline package must currently be installed')
        ident = uuid.uuid4().hex
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        record = {'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'states':states}
        with self.path(ident).open('x',encoding='utf-8') as f: json.dump(record,f)
        return {'baseline_id':ident,'packages':len(states),'created_at':record['created_at']}

    def compare_packages(self, baseline_id):
        record = json.loads(self.path(baseline_id).read_text())
        output = []
        for name,before in record['states'].items():
            try:
                now = read_package(name)
                changed = [key for key in ('status','version') if before.get(key) != now.get(key)]
                output.append({'package':name,'status':'changed' if changed else 'unchanged','changed_fields':changed,'current':now})
            except RuntimeError:
                output.append({'package':name,'status':'unavailable_or_missing'})
        return {'baseline_id':baseline_id,'created_at':record['created_at'],'packages':output,
                'notice':'Read-only Debian package database observations; package integrity and system safety are not established.'}
