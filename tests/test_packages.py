import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('drift_packages_fixture',Path(__file__).parents[1]/'packages.py')
core=importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class PackageTests(unittest.TestCase):
    def test_new_package_baseline_is_private_under_permissive_umask(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            old=os.umask(0)
            try:
                with patch.object(core,'read_package',return_value={'status':'installed','version':'1'}):
                    ident=core.Packages(tmp).baseline_packages(['fixture'])['baseline_id']
                self.assertEqual((Path(tmp)/(ident+'.packages.json')).stat().st_mode & 0o777,0o600)
            finally: os.umask(old)
    def test_baseline_and_version_change(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            plugin=core.Packages(tmp)
            with patch.object(core,'read_package',side_effect=[{'status':'installed','version':'1.0'}, {'status':'installed','version':'2.0'}]):
                baseline=plugin.baseline_packages(['fixture-package'])
                result=plugin.compare_packages(baseline['baseline_id'])
            self.assertEqual(result['packages'][0]['status'],'changed')
            self.assertEqual(result['packages'][0]['changed_fields'],['version'])

    def test_invalid_name_and_missing_package(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            plugin=core.Packages(tmp)
            with self.assertRaises(ValueError): plugin.baseline_packages(['--unsafe'])
            with patch.object(core,'read_package',return_value={'status':'not-installed','version':'1'}):
                with self.assertRaisesRegex(ValueError,'installed'): plugin.baseline_packages(['fixture'])
            with patch.object(core,'read_package',return_value={'status':'installed','version':'1'}):
                baseline=plugin.baseline_packages(['fixture'])
            with patch.object(core,'read_package',side_effect=RuntimeError('unavailable')):
                self.assertEqual(plugin.compare_packages(baseline['baseline_id'])['packages'][0]['status'],'unavailable_or_missing')

    def test_query_environment_excludes_credentials(self):
        response=Mock(returncode=0,stdout=b'installed\t1.0\n')
        with patch.dict(os.environ, {'INWORLD_API_KEY':'fixture-only-value'}), patch.object(core.shutil,'which',return_value='/usr/bin/dpkg-query'), patch.object(core.subprocess,'run',return_value=response) as run:
            self.assertEqual(core.read_package('fixture')['version'],'1.0')
        self.assertNotIn('INWORLD_API_KEY',run.call_args.kwargs['env'])
        self.assertIn('--',run.call_args.args[0])

if __name__=='__main__': unittest.main()
