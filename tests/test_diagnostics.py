from pathlib import Path
import json,os,sys,tempfile,unittest,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e
import safe_store as st
import diagnostics as cw
import profile_backup as pb
from test_components import record,event,s1outcome


class Diagnostics(unittest.TestCase):
    def test_missing_profile_vs_missing_metadata(self):
        self.assertEqual(cw.doctor(self.base/'absent')['status'],'PROFILE_MISSING')
        empty=self.base/'empty';empty.mkdir()
        self.assertEqual(cw.doctor(empty)['status'],'PROFILE_INVALID')

    def test_binding_wrong_shape_and_permission(self):
        path=self.base/'binding.json';path.write_text('[]')
        with patch.object(e,'binding_path',return_value=path):
            self.assertEqual(cw.doctor()['status'],'BINDING_INVALID')
        original=e.read
        with patch.object(e,'binding_path',return_value=path),patch.object(e,'read',side_effect=lambda p: (_ for _ in ()).throw(PermissionError()) if p==path else original(p)):
            self.assertEqual(cw.doctor()['status'],'ACCESS_DENIED')

    def test_deep_valid_readonly(self):
        e.add(self.root,record(text='Synthetic secret body'))
        before=self.snapshot();report=cw.doctor(self.root,True)
        self.assertEqual(report['status'],'OK');self.assertEqual(report['records_validation'],'passed')
        self.assertNotIn('Synthetic secret body',str(report));self.assertEqual(before,self.snapshot())

    def test_cli_unbound_nonzero_and_success_zero(self):
        command=[sys.executable,'-B',str(e.CORE/'scripts/experience.py')]
        env=dict(os.environ,LOCALAPPDATA=str(self.base/'unbound'))
        failed=subprocess.run(command+['doctor'],env=env,capture_output=True,encoding='utf-8')
        self.assertEqual(failed.returncode,1);self.assertEqual(json.loads(failed.stdout)['status'],'UNBOUND')
        good=subprocess.run(command+['--profile',str(self.root),'doctor','--deep'],env=env,capture_output=True,encoding='utf-8')
        self.assertEqual(good.returncode,0,good.stderr);self.assertEqual(json.loads(good.stdout)['status'],'OK')
    def test_direct_cli_help_and_run_discoverable(self):
        env=dict(os.environ,LOCALAPPDATA=str(self.base/'unbound'))
        base=[sys.executable,'-B',str(e.CORE/'scripts/diagnostics.py')]
        shown=subprocess.run(base+['--help'],env=env,capture_output=True,encoding='utf-8',timeout=15)
        self.assertEqual(shown.returncode,0,shown.stderr)
        self.assertIn('--profile',shown.stdout);self.assertIn('--deep',shown.stdout)
        good=subprocess.run(base+['--profile',str(self.root),'--deep'],env=env,capture_output=True,encoding='utf-8',timeout=20)
        self.assertEqual(good.returncode,0,good.stderr);self.assertEqual(json.loads(good.stdout)['status'],'OK')
    def snapshot(self):return pb.inventory(self.root)[0]
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)


    def tearDown(self):self.tmp.cleanup()


    def test_doctor_metadata_only_and_readonly(self):
        before=self.snapshot()
        with patch.object(e,'query',side_effect=AssertionError('Full scan')),patch.object(st,'apply',side_effect=AssertionError('Write')):
            result=cw.doctor(self.root)
        self.assertEqual(result['status'],'OK');self.assertEqual(result['write_access'],'not-tested')
        self.assertEqual(before,self.snapshot())


    def test_doctor_missing_binding_and_invalid_binding(self):
        with patch.object(e,'binding_path',return_value=self.base/'binding.json'):
            self.assertEqual(cw.doctor()['status'],'UNBOUND')
            (self.base/'binding.json').write_text('{}')
            self.assertEqual(cw.doctor()['status'],'BINDING_INVALID')


    def test_doctor_errors_and_deep_validation(self):
        self.assertEqual(cw.doctor(self.base/'missing')['status'],'PROFILE_MISSING')
        with patch.object(st,'pending',return_value=['x']):self.assertEqual(cw.doctor(self.root)['status'],'PENDING_TRANSACTION')
        with patch.object(e,'info',side_effect=PermissionError('private path')):
            result=cw.doctor(self.root);self.assertEqual(result['status'],'ACCESS_DENIED');self.assertNotIn('private path',str(result))
        with patch.object(cw.cp,'verify',side_effect=ValueError('bad')):self.assertEqual(cw.doctor(self.root)['status'],'CORE_INVALID')
        path=self.root/'s1/records'/('a'*32+'.json');path.write_text('{}')
        self.assertEqual(cw.doctor(self.root)['status'],'OK')
        self.assertEqual(cw.doctor(self.root,True)['status'],'PROFILE_INVALID')

    def test_doctor_guidance_incompatible_and_capacity(self):
        with patch.object(e,'info',side_effect=ValueError('Unsupported profile schema or identity')):
            result=cw.doctor(self.root)
            self.assertEqual(result['status'],'PROFILE_INVALID')
            self.assertIn('compatibility-matrix',result['next_step'])
        with patch.object(e,'query',side_effect=ValueError('Profile exceeds capacity limit')):
            result=cw.doctor(self.root,True)
            self.assertEqual(result['status'],'PROFILE_INVALID')
            self.assertIn('容量',result['next_step'])

    def test_doctor_binding_incompatible_guidance(self):
        path=self.base/'binding.json';path.write_text('{}')
        with patch.object(e,'binding_path',return_value=path),patch.object(e,'read',side_effect=ValueError('Unknown installation schema')):
            result=cw.doctor()
            self.assertEqual(result['status'],'BINDING_INVALID')
            self.assertIn('compatibility-matrix',result['next_step'])


    def test_context_failure_diagnostics_are_readonly_and_private(self):
        before=self.snapshot()
        cases=[(PermissionError('secret-path'),'ACCESS_DENIED'),
               (OSError('secret-path'),'BINDING_INVALID'),
               (ValueError('Invalid contexts schema'),'BINDING_INVALID'),
               (ValueError('Links/reparse points are unsupported: secret-path'),'BINDING_INVALID'),
               (ValueError('No context binding for client/account'),'UNBOUND')]
        for exc,status in cases:
            with self.subTest(status=status,error=type(exc).__name__), patch.object(e,'active_context',return_value={'client':'c','account':'a'}), patch.object(e,'resolve_context_root',side_effect=exc), patch.object(st,'apply',side_effect=AssertionError('Write')):
                result=cw.doctor()
                self.assertEqual(result['status'],status)
                self.assertNotIn('secret-path',str(result))
                self.assertEqual(result['core_write_access'],'not-tested')
                self.assertEqual(result['persistence'],'unknown')
        self.assertEqual(before,self.snapshot())

    def test_profile_link_guidance_and_no_write_claim(self):
        with patch.object(e,'profile_root',side_effect=ValueError('Links/reparse points are unsupported: secret-path')):
            result=cw.doctor(self.root)
            self.assertEqual(result['status'],'PROFILE_INVALID')
            self.assertIn('非链接',result['next_step'])
            self.assertNotIn('secret-path',str(result))
        result=cw.doctor(self.root)
        self.assertEqual(result['status'],'OK')
        self.assertEqual(result['write_access'],'not-tested')
        self.assertEqual(result['core_write_access'],'not-tested')
        self.assertEqual(result['persistence'],'unknown')
