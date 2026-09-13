from pathlib import Path
import json,os,sys,tempfile,unittest,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e
import core_package as cp
import diagnostics as d
import recall_view as r
import run_tests
from test_components import record

class AuditFixes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def core(self):
        target=self.base/'core'
        run_tests.prepare(e.CORE,target)
        return target
    def test_failed_add_no_residue_then_init(self):
        root=self.base/'absent'
        with self.assertRaises((ValueError,OSError)):e.add(root,record())
        self.assertFalse(root.exists())
        e.init(root);e.add(root,record())
    def test_invalid_existing_profile_not_overwritten(self):
        root=self.base/'invalid';root.mkdir()
        (root/'profile.json').write_text('{}')
        with self.assertRaises((ValueError,KeyError)):e.add(root,record())
        self.assertEqual((root/'profile.json').read_text(),'{}')
        self.assertFalse((root/'.wb-state').exists())
    def test_host_diagnostic_and_clean_test_copy(self):
        core=self.core();(core/'_user_meta.json').write_text('{}')
        report=d.doctor(self.base/'missing',core=core)
        self.assertEqual(report['checks']['core'],'host-files-only')
        self.assertIn('--allow-host-files',report['next_step'])
        self.assertEqual(d.doctor(self.base/'missing',core=core,allow_host_files=True)['status'],'PROFILE_MISSING')
        copy=run_tests.prepare(core,self.base/'copy')
        self.assertFalse((copy/'_user_meta.json').exists())
        self.assertEqual(cp.verify(core,True)['sha256'],cp.verify(copy)['sha256'])
    def test_host_plus_tampering_not_misdiagnosed(self):
        core=self.core();(core/'_user_meta.json').write_text('{}')
        (core/'SKILL.md').write_text('tampered')
        report=d.doctor(self.base/'missing',core=core)
        self.assertNotEqual(report['checks'].get('core'),'host-files-only')
        with self.assertRaises(ValueError):run_tests.prepare(core,self.base/'copy')
    def test_unknown_files_rejected(self):
        core=self.core();(core/'unknown.py').write_text('pass')
        with self.assertRaises(ValueError):run_tests.prepare(core,self.base/'copy')
        self.assertEqual(d.doctor(core=core,allow_host_files=True)['status'],'CORE_INVALID')
    def test_host_named_hardlink_rejected(self):
        core=self.core();outside=self.base/'outside';outside.write_text('{}')
        os.link(outside,core/'_user_meta.json')
        with self.assertRaises((ValueError,OSError)):run_tests.prepare(core,self.base/'copy')
    def test_default_three_cli_and_explicit_expansion(self):
        root=self.base/'profile';e.init(root)
        for i in range(7):e.add(root,record(state='confirmed',confirmed_by='synthetic',text='sample '+str(i)))
        self.assertEqual(len(r.recall(root)['items']),3)
        self.assertEqual(len(r.recall(root,limit=7,max_chars=5000)['items']),7)
        cmd=[sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(root),'recall']
        result=subprocess.run(cmd,capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['items']),3)
        self.assertLessEqual(len(result.stdout),3000)
    def test_outcome_commands_retired_without_writes(self):
        root=self.base/'profile';e.init(root)
        before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        for command in ('observe-s1','observe-s2'):
            result=subprocess.run([sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(root),command,'missing.json'],capture_output=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('retired',result.stderr)
        after={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_policy_development_and_public(self):
        if (e.CORE/'scripts/build_public.py').exists():
            from build_public import PUBLIC_SKILL
        else:PUBLIC_SKILL=(e.CORE/'SKILL.md').read_text(encoding='utf-8')
        skill=(e.CORE/'SKILL.md').read_text(encoding='utf-8')
        for text in (skill,PUBLIC_SKILL):
            self.assertIn('3条/3000字符',text)
        self.assertNotIn('效果样本检查（开发验证阶段的固定动作',skill)
        self.assertIn('同一任务复用',skill)
