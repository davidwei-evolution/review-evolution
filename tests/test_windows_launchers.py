from pathlib import Path
import sys,tempfile,unittest,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import check_windows_launchers as cl

GOOD=('@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\n'
      '> "验收日志.txt" echo start\r\n'
      'echo running\r\n'
      'pause\r\nexit /b 0\r\n')

def variant(text):
    return text.replace('\r\n','\n')

class WindowsLaunchers(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def folder(self,name,text,raw=None):
        target=self.base/name;target.mkdir(parents=True,exist_ok=True)
        (target/'run.bat').write_bytes(raw if raw is not None else text.encode('utf-8'))
        return target

    def rules(self,target):
        report=cl.check(target)
        return report,[r for f in report['findings'] for r in f['rules']]

    def test_crlf_launcher_with_pause_and_output_passes(self):
        report,rules=self.rules(self.folder('good',GOOD))
        self.assertEqual(report['status'],'PASS');self.assertEqual(report['launchers'],1);self.assertEqual(rules,[])

    def test_bare_lf_line_endings_rejected(self):
        _report,rules=self.rules(self.folder('lf',variant(GOOD)))
        self.assertIn('bare-lf-line-endings',rules)

    def test_utf8_bom_rejected(self):
        _report,rules=self.rules(self.folder('bom',GOOD,raw=b'\xef\xbb\xbf'+GOOD.encode('utf-8')))
        self.assertIn('utf8-bom',rules)

    def test_exit_without_pause_rejected(self):
        text=GOOD.replace('pause\r\nexit /b 0\r\n','exit /b 0\r\n')
        _report,rules=self.rules(self.folder('nopause',text))
        self.assertIn('exit-without-pause',rules);self.assertIn('no-pause',rules)

    def test_missing_persisted_output_rejected(self):
        text=GOOD.replace('> "验收日志.txt" echo start\r\n','')
        _report,rules=self.rules(self.folder('noout',text))
        self.assertIn('no-persisted-output',rules)

    def test_folder_without_launchers_is_not_a_failure(self):
        empty=self.base/'empty';empty.mkdir()
        report,rules=self.rules(empty)
        self.assertEqual(report['status'],'PASS');self.assertEqual(report['launchers'],0);self.assertEqual(rules,[])

    def test_zip_target_is_scanned_without_extracting(self):
        target=self.base/'pkg.zip'
        with zipfile.ZipFile(target,'w') as z:
            z.writestr('run.cmd',variant(GOOD));z.writestr('使用说明.md','doc')
        report,rules=self.rules(target)
        self.assertEqual(report['launchers'],1);self.assertEqual(report['status'],'FAIL')
        self.assertIn('bare-lf-line-endings',rules)

    def test_non_launcher_target_rejected(self):
        with self.assertRaises(ValueError):cl.check(self.base/'missing-path')
