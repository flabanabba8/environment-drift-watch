import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('drift_services_fixture',Path(__file__).parents[1]/'services.py')
core=importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class ServiceTests(unittest.TestCase):
    def test_new_service_baseline_is_private_under_permissive_umask(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            old=os.umask(0)
            try:
                with patch.object(core,'read_service',return_value={'LoadState':'loaded','ActiveState':'active'}):
                    ident=core.Services(tmp).baseline_services(['fixture.service'])['baseline_id']
                self.assertEqual((Path(tmp)/(ident+'.services.json')).stat().st_mode & 0o777,0o600)
            finally: os.umask(old)
    def test_baseline_and_change_without_mutation(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            plugin=core.Services(tmp)
            initial={'LoadState':'loaded','ActiveState':'active','SubState':'running','UnitFileState':'enabled','ActiveEnterTimestampMonotonic':'10'}
            changed={**initial,'ActiveState':'failed','SubState':'failed'}
            with patch.object(core,'read_service',side_effect=[initial,changed]):
                baseline=plugin.baseline_services(['fixture.service'])
                result=plugin.compare_services(baseline['baseline_id'])
            self.assertEqual(result['services'][0]['status'],'changed')
            self.assertIn('ActiveState',result['services'][0]['changed_fields'])

    def test_invalid_units_and_unavailable_service(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            plugin=core.Services(tmp)
            with self.assertRaises(ValueError): plugin.baseline_services(['../unsafe.service'])
            with patch.object(core,'read_service',return_value={'LoadState':'not-found','ActiveState':'inactive'}):
                with self.assertRaisesRegex(ValueError,'loaded'): plugin.baseline_services(['missing.service'])
            with patch.object(core,'read_service',return_value={'LoadState':'loaded','ActiveState':'active'}):
                baseline=plugin.baseline_services(['fixture.service'])
            with patch.object(core,'read_service',side_effect=RuntimeError('unavailable')):
                self.assertEqual(plugin.compare_services(baseline['baseline_id'])['services'][0]['status'],'unavailable')

    def test_subprocess_receives_no_credential_values(self):
        response=Mock(returncode=0,stdout=b'LoadState=loaded\nActiveState=active\n')
        with patch.dict(os.environ, {'INWORLD_API_KEY':'fixture-only-value'}), patch.object(core.shutil,'which',return_value='/usr/bin/systemctl'), patch.object(core.subprocess,'run',return_value=response) as run:
            state=core.read_service('user','fixture.service')
        self.assertEqual(state['ActiveState'],'active')
        self.assertNotIn('INWORLD_API_KEY',run.call_args.kwargs['env'])
        self.assertIn('--',run.call_args.args[0])

if __name__=='__main__': unittest.main()
