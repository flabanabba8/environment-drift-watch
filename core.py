"""A hash-only baseline for explicitly selected regular files."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

PRIVATE = {'.ssh', '.gnupg', '.aws', '.azure', '.codex', '.docker', '.kube', '.pki', '.config', '.hermes'}
MAX_FILE = 256 * 1024**2


def measure(path):
    p = Path(path).expanduser()
    if not p.is_absolute() or any(x in PRIVATE for x in p.parts):
        raise ValueError('Use absolute paths outside private configuration')
    if p.is_symlink():
        raise ValueError('Symlink inputs are unsupported')
    p = p.resolve(strict=True)
    if any(x in PRIVATE for x in p.parts):
        raise ValueError('Private configuration paths are unsupported')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    h = hashlib.sha256()
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
            raise ValueError('Only regular files up to 256 MiB are supported')
        total = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            total += len(chunk)
            if total > MAX_FILE: raise ValueError('File exceeds 256 MiB while measuring')
            h.update(chunk)
        after = os.fstat(stream.fileno())
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode, value.st_uid, value.st_gid)
    current = p.lstat()
    if fields(before) != fields(after) or fields(after) != fields(current) or not stat.S_ISREG(current.st_mode):
        raise ValueError('File changed while measuring')
    return {'sha256': h.hexdigest(), 'size': after.st_size, 'mode': stat.S_IMODE(after.st_mode),
            'uid': after.st_uid, 'gid': after.st_gid}


class Drift:
    def __init__(self, root):
        self.root = Path(root)

    def baseline(self, paths):
        if not isinstance(paths, list) or not 1 <= len(paths) <= 1000 or any(not isinstance(x, str) for x in paths):
            raise ValueError('Provide 1–1000 file paths')
        canonical = [str(Path(x).expanduser()) for x in paths]
        if len(set(canonical)) != len(canonical):
            raise ValueError('Duplicate paths')
        files = {path: measure(path) for path in canonical}
        baseline_id = uuid.uuid4().hex
        record = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': files}
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(os.open(self.root / (baseline_id + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as f:
            json.dump(record, f)
        return {'baseline_id': baseline_id, 'created_at': record['created_at'], 'files': len(files)}

    def list_baselines(self):
        if not self.root.exists(): return {'baselines': [], 'unreadable_records': 0}
        paths = sorted(self.root.glob('*.json'))
        if len(paths) > 1000: raise ValueError('More than 1,000 baseline files; narrow the directory first')
        output, unreadable = [], 0
        for path in paths:
            match = re.fullmatch(r'([0-9a-f]{32})(?:\.(packages|services))?\.json', path.name)
            if not match: continue
            try:
                if path.is_symlink(): raise ValueError('Symlink baseline')
                record = json.loads(path.read_text(encoding='utf-8'))
                kind = match.group(2) or 'files'
                values = record['files'] if kind == 'files' else record['states']
                if not isinstance(values, dict): raise ValueError('Invalid baseline')
                output.append({'baseline_id': match.group(1), 'kind': kind, 'created_at': record['created_at'], 'items': len(values)})
            except (OSError, ValueError, KeyError, TypeError):
                unreadable += 1
        return {'baselines': output, 'unreadable_records': unreadable}

    def compare(self, baseline_id):
        if not isinstance(baseline_id, str) or len(baseline_id) != 32 or any(c not in '0123456789abcdef' for c in baseline_id):
            raise ValueError('Invalid baseline ID')
        path = self.root / (baseline_id + '.json')
        if path.is_symlink():
            raise ValueError('Invalid baseline path')
        record = json.loads(path.read_text(encoding='utf-8'))
        findings = []
        for name, before in record['files'].items():
            try:
                now = measure(name)
                fields = ('sha256', 'size', 'mode', 'uid', 'gid')
                changed = [k for k in fields if k in before and before[k] != now[k]]
                unrecorded = [k for k in fields if k not in before]
                status = 'changed' if changed else 'unchanged_in_recorded_fields' if unrecorded else 'unchanged'
                findings.append({'path': name, 'status': status, 'changed_fields': changed,
                                 'unrecorded_fields': unrecorded})
            except FileNotFoundError:
                findings.append({'path': name, 'status': 'missing'})
            except (OSError, ValueError):
                findings.append({'path': name, 'status': 'inaccessible_or_unsupported'})
        return {'baseline_id': baseline_id, 'created_at': record['created_at'], 'files': findings}
