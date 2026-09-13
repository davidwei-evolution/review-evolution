"""Public packages must not inherit local development history or maintainer procedures."""
from pathlib import Path
import os,subprocess,sys,tempfile,unittest
import json

CORE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CORE/'scripts'))


class PublicContentBoundary(unittest.TestCase):
    def setUp(self):
        try:
            import build_public
        except ModuleNotFoundError:
            self.skipTest('Public candidate: the development builder is intentionally absent')
        self.builder=build_public
        self.tmp=tempfile.TemporaryDirectory()

    def tearDown(self):
        if hasattr(self,'tmp'):self.tmp.cleanup()

    def test_public_documents_are_generated_for_users_not_copied_from_development_history(self):
        out=Path(self.tmp.name)/'base'
        self.builder.build(CORE,out)
        for rel in ('references/release-check.md','references/installer-review-template.md',
                    'references/client-acceptance.md','references/compatibility-matrix.md',
                    'references/host-integration.md','references/conversations/index.md',
                    'references/conversations/s2-hit-register.md'):
            self.assertFalse((out/rel).exists(),rel)
        changelog=(out/'CHANGELOG.md').read_text(encoding='utf-8')
        known=(out/'KNOWN_ISSUES.md').read_text(encoding='utf-8')
        self.assertTrue(changelog.startswith('# 更新说明'))
        self.assertIn('相对上一个正式发布版本',changelog)
        self.assertNotIn('S3明确可选安装',changelog)
        self.assertTrue(known.startswith('# 当前已知限制'))
        self.assertNotIn('## fixed',known)
        self.assertNotIn('v0.22',known)

    def test_public_package_carries_no_trace_of_the_internal_module(self):
        """2026-09-13 用户要求：对外只有单一形态，用户可见面不得出现内部模块的任何痕迹。"""
        out=Path(self.tmp.name)/'single'
        self.builder.build(CORE,out)
        self.assertFalse((out/'scripts/s3_optional.py').exists())
        self.assertFalse((out/'references/s3-issues.md').exists())
        self.assertFalse((out/'scripts/install_bundle.py').exists())
        self.assertEqual(json.loads((out/'runtime-policy.json').read_text(encoding='utf-8')),
                         {'schema':1,'edition':'public'})
        offenders=[]
        for path in out.rglob('*'):
            if path.is_file() and path.suffix in ('.md','.json') and path.name!='CORE.json':
                if 's3' in path.read_text(encoding='utf-8').lower():
                    offenders.append(path.relative_to(out).as_posix())
        self.assertEqual([],offenders)

    def test_gate_rejects_development_documents_or_history_if_they_reenter_a_public_candidate(self):
        import release_gate as gate
        out=Path(self.tmp.name)/'base'
        self.builder.build(CORE,out)
        payload={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertFalse(any(f['rule'].startswith('public-development') for f in gate.scan_payload(payload)['findings']))
        payload['references/release-check.md']=b'# development only\n'
        meta=json.loads(payload['CORE.json'])
        meta['files']['references/release-check.md']=gate.st.digest(payload['references/release-check.md'])
        payload['CORE.json']=gate.st.json_bytes(meta)
        rules=[f['rule'] for f in gate.scan_payload(payload)['findings']]
        self.assertIn('public-development-document',rules)

    def test_gate_rejects_any_internal_module_trace_in_a_public_package(self):
        import release_gate as gate
        out=Path(self.tmp.name)/'single'
        self.builder.build(CORE,out)
        payload={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertFalse(any(f['rule']=='optional-module-trace'
                             for f in gate.scan_payload(payload)['findings']))
        trace='内部备注：'+'s'+'3'+' 模块说明\n'
        payload['README.md']=payload['README.md']+trace.encode()
        meta=json.loads(payload['CORE.json'])
        meta['files']['README.md']=gate.st.digest(payload['README.md'])
        payload['CORE.json']=gate.st.json_bytes(meta)
        rules=[f['rule'] for f in gate.scan_payload(payload)['findings']]
        self.assertIn('optional-module-trace',rules)

    def test_public_runtime_output_carries_no_internal_module_trace(self):
        """真机反馈 F2（2026-09-13）：静态文件干净还不够，运行期输出也必须零痕迹。"""
        out=Path(self.tmp.name)/'runtime-candidate'
        self.builder.build(CORE,out)
        work=Path(self.tmp.name)/'runtime-local';work.mkdir()
        env=dict(os.environ,LOCALAPPDATA=str(work),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
        profile=work/'profile'

        def run(*args):
            return subprocess.run([sys.executable,'-B',str(out/'scripts/experience.py'),
                                   '--profile',str(profile),*args],
                                  capture_output=True,text=True,encoding='utf-8',
                                  errors='replace',env=env,timeout=120)

        run('init')
        for args in (('doctor',),('status',),('intro',),('plan-backup',),('overview',)):
            with self.subTest(args=args):
                proc=run(*args)
                text=((proc.stdout or '')+(proc.stderr or '')).lower()
                self.assertNotIn('s3',text)

    def test_release_notes_text_may_name_the_stable_baseline_but_not_development_history(self):
        src=Path(self.tmp.name)/'src';(src/'references').mkdir(parents=True)

        def write(text):
            (src/'references'/'public-release-notes.json').write_text(json.dumps(
                {'schema':1,'from_version':'1.0.0','to_version':'9.9.9',
                 'changes':[{'kind':'changed','text':text}]},ensure_ascii=False),encoding='utf-8')
            return self.builder.public_release_notes(src,'9.9.9')

        row=write('升级兼容范围从 1.0.0 起：更早版本仍可升级，但不再作为保证范围。')
        self.assertEqual(row['to_version'],'9.9.9')
        for blocked in ('本版相对 0.22.6 的变化','升级自 v0.21.5 起'):
            with self.subTest(blocked=blocked):
                with self.assertRaises(ValueError):write(blocked)


if __name__=='__main__':unittest.main()
