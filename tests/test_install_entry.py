"""Install-entry regressions (D1/D2, 2026-09-12).

Static checks prove the one-call install entry exists and that the documented new-install
path checks for an existing binding before creating a profile. The runtime check actually
runs scripts/re-cli.ps1 -InstallAll against a throw-away LOCALAPPDATA, so a broken
orchestration fails here instead of on a user's machine.
"""
from pathlib import Path
import json,os,shutil,subprocess,tempfile,unittest

CORE=Path(__file__).resolve().parents[1]

def powershell():
    for name in ('pwsh','powershell'):
        found=shutil.which(name)
        if found:
            return found
    return None

class InstallEntryStatic(unittest.TestCase):
    def setUp(self):
        self.launcher=(CORE/'scripts'/'re-cli.ps1').read_text(encoding='utf-8')
        self.install=(CORE/'references'/'install.md').read_text(encoding='utf-8')

    def test_launcher_has_a_one_call_install(self):
        self.assertIn('[switch]$InstallAll',self.launcher)
        self.assertIn('installation.json',self.launcher)
        self.assertIn('core_package.py',self.launcher)
        self.assertIn('doctor',self.launcher)

    def test_launcher_does_not_promise_a_single_host_prompt(self):
        # The host decides how often it asks; no user-facing line may claim otherwise.
        # Comment lines are excluded because they exist to explain this very limitation.
        code='\n'.join(line for line in self.launcher.splitlines()
                       if not line.strip().startswith('#'))
        lowered=code.casefold()
        self.assertNotIn('only once',lowered)
        self.assertNotIn('single prompt',lowered)

    def test_documented_new_install_checks_the_binding_first(self):
        step=self.install.index('新装第一步（必做）')
        flow=self.install.index('新装：以 zip 为唯一安装源')
        self.assertLess(step,flow,'binding precheck must be documented before the install flow')
        block=self.install[step:flow]
        self.assertIn('installation.json',block)
        self.assertIn('跳过 init',block)

class InstallEntryRuntime(unittest.TestCase):
    def setUp(self):
        exe=powershell()
        if exe is None:
            self.skipTest('no PowerShell available')
        self.exe=exe
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self):
        env=dict(os.environ)
        env['LOCALAPPDATA']=str(self.base)
        env['PYTHONUTF8']='1'
        for key in ('REVIEW_EVOLUTION_CLIENT','REVIEW_EVOLUTION_ACCOUNT','REVIEW_EVOLUTION_PYTHON'):
            env.pop(key,None)
        return subprocess.run([self.exe,'-NoProfile','-ExecutionPolicy','Bypass','-File',
                               str(CORE/'scripts'/'re-cli.ps1'),'-InstallAll'],
                              capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)

    def test_install_all_binds_once_then_reuses_the_same_profile(self):
        first=self.run_install()
        self.assertEqual(0,first.returncode,(first.stdout or '')+(first.stderr or ''))
        install=self.base/'review-evolution'/'installation.json'
        self.assertTrue(install.exists(),'install did not write a local binding')
        bound=json.loads(install.read_text(encoding='utf-8'))['profile_root']
        profile=Path(bound)
        self.assertTrue((profile/'profile.json').exists())
        revision=json.loads((profile/'profile.json').read_text(encoding='utf-8'))['revision']
        second=self.run_install()
        self.assertEqual(0,second.returncode,(second.stdout or '')+(second.stderr or ''))
        self.assertIn('existing profile found',second.stdout)
        self.assertEqual(bound,json.loads(install.read_text(encoding='utf-8'))['profile_root'])
        self.assertEqual(revision,json.loads((profile/'profile.json').read_text(encoding='utf-8'))['revision'],
                         'second run must not touch the existing profile')

if __name__=='__main__':
    unittest.main()
