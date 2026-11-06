"""Read-only snapshots of explicitly selected systemd service states."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

FIELDS = ('LoadState', 'ActiveState', 'SubState', 'UnitFileState', 'ActiveEnterTimestampMonotonic')
UNIT = re.compile(r'[A-Za-z0-9_.@:-]{1,200}\.service')


def read_service(scope, unit):
    binary = shutil.which('systemctl')
    if not binary: raise RuntimeError('systemctl is unavailable')
    env = {k: os.environ[k] for k in ('HOME','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','LANG') if k in os.environ}
    env['PATH'] = os.defpath
    args = [binary, '--user' if scope == 'user' else '--system', 'show', '--no-pager',
            *['--property='+field for field in FIELDS], '--', unit]
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Service state could not be read') from exc
    if result.returncode or len(result.stdout) > 8192: raise RuntimeError('Service state could not be read')
    values = {}
    try:
        for line in result.stdout.decode('utf-8').splitlines():
            key, sep, value = line.partition('=')
            if sep and key in FIELDS and len(value) <= 256: values[key] = value
    except UnicodeError as exc:
        raise RuntimeError('Service state was not valid text') from exc
    if 'LoadState' not in values or 'ActiveState' not in values: raise RuntimeError('Service state is incomplete')
    return values


class Services:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, baseline_id):
        if not isinstance(baseline_id, str) or len(baseline_id) != 32 or any(c not in '0123456789abcdef' for c in baseline_id):
            raise ValueError('Invalid service baseline ID')
        path = self.root/(baseline_id+'.services.json')
        if path.is_symlink(): raise ValueError('Invalid service baseline')
        return path

    def baseline_services(self, units, scope='user'):
        if scope not in ('user','system') or not isinstance(units, list) or not 1 <= len(units) <= 20 or any(not isinstance(x,str) or not UNIT.fullmatch(x) for x in units) or len(set(units)) != len(units):
            raise ValueError('Choose 1–20 distinct explicit .service names and user or system scope')
        states = {unit: read_service(scope, unit) for unit in units}
        if any(state['LoadState'] != 'loaded' for state in states.values()):
            raise ValueError('Every baseline service must currently be loaded')
        ident = uuid.uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {'scope':scope,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'states':states}
        with os.fdopen(os.open(self.path(ident), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as f: json.dump(record,f)
        return {'baseline_id':ident,'scope':scope,'services':len(states),'created_at':record['created_at']}

    def compare_services(self, baseline_id):
        record = json.loads(self.path(baseline_id).read_text())
        output = []
        for unit, before in record['states'].items():
            try:
                now = read_service(record['scope'], unit)
                changed = [field for field in FIELDS if before.get(field) != now.get(field)]
                status = 'changed' if changed else 'unchanged'
                output.append({'service':unit,'status':status,'changed_fields':changed,'current':now})
            except RuntimeError:
                output.append({'service':unit,'status':'unavailable'})
        return {'baseline_id':baseline_id,'scope':record['scope'],'created_at':record['created_at'],'services':output,
                'notice':'Read-only point-in-time observations; service health and configuration correctness are not established.'}
