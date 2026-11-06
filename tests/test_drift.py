import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('drift_core', Path(__file__).parents[1] / 'core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class DriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp')
        self.root = Path(self.tmp.name)
        self.a, self.b = self.root / 'a', self.root / 'b'
        self.a.write_text('initial')
        self.b.write_text('unchanged')
        self.drift = core.Drift(self.root / 'baselines')
        self.id = self.drift.baseline([str(self.a), str(self.b)])['baseline_id']

    def tearDown(self):
        self.tmp.cleanup()

    def test_changed_missing_and_hash_only(self):
        record = (self.root / 'baselines' / (self.id + '.json')).read_text()
        self.assertNotIn('initial', record)
        self.a.write_text('modified')
        self.b.unlink()
        findings = self.drift.compare(self.id)['files']
        self.assertEqual([x['status'] for x in findings], ['changed', 'missing'])
        self.assertIn('sha256', findings[0]['changed_fields'])

    def test_mode_and_symlink(self):
        os.chmod(self.a, 0o600)
        self.assertIn('mode', self.drift.compare(self.id)['files'][0]['changed_fields'])
        self.b.unlink()
        self.b.symlink_to(self.a)
        self.assertEqual(self.drift.compare(self.id)['files'][1]['status'], 'inaccessible_or_unsupported')

    def test_older_baselines_do_not_claim_ownership_was_checked(self):
        import json
        path = self.root / 'baselines' / (self.id + '.json')
        record = json.loads(path.read_text())
        for item in record['files'].values():
            item.pop('uid'); item.pop('gid')
        path.write_text(json.dumps(record))
        result = self.drift.compare(self.id)['files'][0]
        self.assertEqual(result['status'], 'unchanged_in_recorded_fields')
        self.assertEqual(result['unrecorded_fields'], ['uid', 'gid'])

    def test_owner_change_is_reported(self):
        import json
        path = self.root / 'baselines' / (self.id + '.json')
        record = json.loads(path.read_text())
        record['files'][str(self.a)]['uid'] += 1
        path.write_text(json.dumps(record))
        self.assertIn('uid', self.drift.compare(self.id)['files'][0]['changed_fields'])

    def test_replaced_during_hashing_is_rejected(self):
        replacement = self.root / 'replacement'; replacement.write_text('different')
        original = core.os.fstat
        calls = 0
        def replace(fd):
            nonlocal calls
            calls += 1
            value = original(fd)
            if calls == 2: core.os.replace(replacement, self.a)
            return value
        with patch.object(core.os, 'fstat', side_effect=replace):
            with self.assertRaisesRegex(ValueError, 'changed while measuring'): core.measure(str(self.a))

    def test_recover_baseline_id_without_exposing_file_paths(self):
        root = self.root / 'baselines'
        import json
        (root / ('a'*32 + '.services.json')).write_text(json.dumps({'created_at':'2026-01-01', 'states': {'example.service': {}}}))
        (root / ('b'*32 + '.packages.json')).write_text(json.dumps({'created_at':'2026-01-01', 'states': {'example': {}}}))
        result = self.drift.list_baselines()
        records = {x['baseline_id']: x['kind'] for x in result['baselines']}
        self.assertEqual(records[self.id], 'files')
        self.assertEqual(records['a'*32], 'services')
        self.assertEqual(records['b'*32], 'packages')
        self.assertNotIn(str(self.a), str(result))

if __name__ == '__main__':
    unittest.main()
