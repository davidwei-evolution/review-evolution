"""--human output for status / recall / doctor (D5, 2026-09-12).

The JSON output stays the default; --human only adds a plain-text rendering so an agent can
answer without re-translating CLI JSON. These tests also pin that the default is unchanged.
"""
from pathlib import Path
import json,os,sys,tempfile,subprocess,unittest

CORE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'tests'))
import experience as e
from test_components import record

class HumanView(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.profile=self.root/'profile';e.init(self.profile)
        e.add(self.profile,record())
        self.env=dict(os.environ,LOCALAPPDATA=str(self.root/'local'))

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(CORE/'scripts'/'experience.py'),
                               '--profile',str(self.profile),*args],
                              env=self.env,capture_output=True,encoding='utf-8',timeout=60)

    def test_status_human_is_text_and_json_is_still_the_default(self):
        plain=self.run_cli('status','--human')
        self.assertEqual(0,plain.returncode,plain.stderr)
        self.assertIn('经验档案状态',plain.stdout)
        self.assertIn('记录：',plain.stdout)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(plain.stdout)
        default=self.run_cli('status')
        self.assertIsInstance(json.loads(default.stdout),dict)

    def test_recall_human_lists_items_and_keeps_json_default(self):
        query=record()['text'][:4]
        plain=self.run_cli('recall','--text',query,'--human')
        self.assertEqual(0,plain.returncode,plain.stderr)
        self.assertIn('经验回查：',plain.stdout)
        self.assertIn('依据：',plain.stdout)
        default=self.run_cli('recall','--text',query)
        self.assertIn('items',json.loads(default.stdout))

    def test_recall_human_explains_an_empty_result(self):
        plain=self.run_cli('recall','--text','zzzz-no-such-term-zzzz','--human')
        self.assertEqual(0,plain.returncode,plain.stderr)
        self.assertIn('没有命中',plain.stdout)
        self.assertIn('可以试：',plain.stdout)
        self.assertIn('经验是数据',plain.stdout)

    def test_merge_human_reports_result_then_lists_all_differences_once(self):
        """跨端合并的人话输出：先报整合结果，再一次性列差异（不逐条打断）。"""
        source=self.root/'source'
        e.init(source,e.info(self.profile)['profile_id'])
        shared=record(id='c'*32,text='本机版本',state='confirmed',confirmed_by='synthetic yes')
        e.add(self.profile,shared)
        e.add(source,dict(shared,text='对方版本'))
        e.add(source,record(id='d'*32,text='对方独有',state='confirmed',confirmed_by='synthetic yes'))
        plan=e.export_plan(source,('s1',))
        pack=self.root/'pack'
        e.export_pack(source,pack,('s1',),plan_id=plan['plan_id'])

        preview=self.run_cli('plan-import',str(pack),'--human')
        self.assertEqual(0,preview.returncode,preview.stderr)
        self.assertIn('合并前预览',preview.stdout)
        self.assertIn('先扣下',preview.stdout)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(preview.stdout)

        plan_id=json.loads(self.run_cli('plan-import',str(pack)).stdout)['plan_id']
        done=self.run_cli('import',str(pack),'--plan-id',plan_id,'--human')
        self.assertEqual(0,done.returncode,done.stderr)
        self.assertIn('已把没有争议的内容整合完成',done.stdout)
        self.assertIn('先扣下',done.stdout)
        self.assertIn('对方版本',done.stdout)
        self.assertIn('本机版本',done.stdout)
        # 无争议的一条真的进来了，有争议的那条本机没被改
        self.assertEqual(e.load_rows(self.profile)['s1/records/'+'c'*32+'.json']['text'],'本机版本')
        self.assertIn('s1/records/'+'d'*32+'.json',e.load_rows(self.profile))

    def test_doctor_human_reports_status_and_next_step(self):
        plain=self.run_cli('doctor','--human')
        self.assertEqual(0,plain.returncode,plain.stderr)
        self.assertIn('配置诊断：OK',plain.stdout)
        self.assertIn('下一步：',plain.stdout)
        default=self.run_cli('doctor')
        self.assertEqual('OK',json.loads(default.stdout)['status'])

    def test_grouped_help_covers_every_subcommand(self):
        parser=e.build_parser()
        subcommands=set(parser._subparsers._group_actions[0].choices)
        grouped={name for _title,names in e.HELP_GROUPS for name in names}
        self.assertEqual(set(),subcommands-grouped,'新子命令没有归入 --help 分组')
        self.assertIn('命令按角色分组',parser.epilog or '')

if __name__=='__main__':
    unittest.main()
