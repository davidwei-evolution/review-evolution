from pathlib import Path
import json,os,sys,tempfile,unittest,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
import safe_store as st
from test_components import record,event


class ArchiveReminder(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def prefs(self,count,start=0):
        for i in range(start,start+count):
            e.add_event(self.root,event(source=f'synthetic:{i}',preference_id=f'pref{i}',
                                        module='documents',text=f'Preference {i}'))

    def mark_success(self,days_ago,path=None):
        at='2026-06-01T00:00:00Z' if days_ago is None else \
            '2026-01-01T00:00:00Z' if days_ago>=150 else '2026-09-01T00:00:00Z'
        payload={'state':'success','at':at}
        if path is not None:payload['archive_path']=path
        return e.archive_mark(self.root,payload)

    def state(self):
        return e.load_archive_state(self.root)

    def test_new_empty_profile_not_due_and_status_is_readonly(self):
        result=e.archive_status(self.root)
        self.assertFalse(result['due']);self.assertEqual(result['reasons'],[])
        self.assertFalse((self.root/'reminders/archive.json').exists())

    def test_first_advice_requires_five_confirmed_preferences(self):
        self.prefs(4)
        self.assertFalse(e.archive_status(self.root)['due'])
        self.prefs(1,start=4)
        result=e.archive_status(self.root)
        self.assertTrue(result['due']);self.assertEqual([r['condition'] for r in result['reasons']],['A'])

    def test_advised_once_stops_repeat(self):
        self.prefs(5)
        e.archive_mark(self.root,{'state':'advised','at':'2026-09-09T00:00:00Z'})
        result=e.archive_status(self.root)
        self.assertFalse(result['due']);self.assertEqual(result['reasons'],[])
        self.assertEqual(self.state()['last_advised_state'],'advised')
        self.prefs(3)
        self.assertFalse(e.archive_status(self.root)['due'])

    def test_declined_and_disabled(self):
        self.prefs(5)
        e.archive_mark(self.root,{'state':'declined','at':'2026-09-09T00:00:00Z'})
        self.assertFalse(e.archive_status(self.root)['due'])
        e.archive_mark(self.root,{'state':'advised','at':'2026-09-09T00:00:00Z','enabled':False})
        self.assertFalse(e.archive_status(self.root)['due'])
        self.assertFalse(self.state()['enabled'])

    def test_success_sets_baseline_and_B_after_interval(self):
        e.add(self.root,record())
        result=self.mark_success(200,path='synthetic-archive-2026/backup')
        self.assertEqual(result['state'],'success');self.assertEqual(result['baseline']['records'],1)
        status=e.archive_status(self.root)
        self.assertTrue(status['due']);self.assertEqual([r['condition'] for r in status['reasons']],['B'])
        self.assertEqual(status['archive_version'],e._current_core_version())
        self.assertEqual(self.state()['last_archive_path'],'synthetic-archive-2026/backup')

    def test_D_record_delta(self):
        e.add(self.root,record())
        self.mark_success(200)
        for i in range(55):
            e.add(self.root,record(text=f'Extra {i}',task_id=f'extra-{i}'))
        status=e.archive_status(self.root)
        self.assertTrue(status['due'])
        conditions={r['condition'] for r in status['reasons']}
        self.assertIn('B',conditions);self.assertIn('D',conditions)

    def test_D_preference_delta_branch(self):
        e.add(self.root,record())
        self.mark_success(200)
        self.prefs(11)
        conditions={r['condition'] for r in e.archive_status(self.root)['reasons']}
        self.assertIn('D',conditions)

    def test_C_core_change_only_after_cooldown(self):
        e.add(self.root,record())
        self.mark_success(200)
        with patch.object(e,'_current_core_version',return_value=e._current_core_version()+'-different'):
            status=e.archive_status(self.root)
            self.assertTrue(status['due'])
            self.assertIn('C',{r['condition'] for r in status['reasons']})
        self.mark_success(0)
        with patch.object(e,'_current_core_version',return_value=e._current_core_version()+'-different'):
            self.assertNotIn('C',{r['condition'] for r in e.archive_status(self.root)['reasons']})

    def test_mark_validation_and_value_overrides(self):
        with self.assertRaises(ValueError):e.archive_mark(self.root,{'state':'later'})
        with self.assertRaises(ValueError):e.archive_mark(self.root,{'state':'advised','at':'2026-09-09'})
        e.archive_mark(self.root,{'state':'advised','at':'2026-09-09T00:00:00Z',
                                  'interval_days':180,'activity_delta_records':20})
        state=self.state()
        self.assertEqual(state['interval_days'],180);self.assertEqual(state['activity_delta_records'],20)

    def test_target_check_accepts_parent_and_suggests_child(self):
        parent=self.base/'parent';parent.mkdir()
        result=e.archive_target_check(self.root,parent)
        self.assertTrue(result['ok']);self.assertTrue(result['target'].startswith(str(parent)))
        self.assertEqual(len(result['suggested_child']),len('review-evolution-backup-12345678-2026-09-09'))
        # Re-running with the same day avoids an existing target by suffixing.
        (parent/result['suggested_child']).mkdir()
        second=e.archive_target_check(self.root,parent)
        self.assertNotEqual(second['suggested_child'],result['suggested_child'])

    def test_target_check_rejects_unsafe_or_unsuitable_parents(self):
        relative=e.archive_target_check(self.root,'relative\\folder')
        self.assertFalse(relative['ok']);self.assertEqual(relative['checks'][0]['name'],'absolute')
        missing=e.archive_target_check(self.root,self.base/'missing')
        self.assertFalse(missing['ok'])
        core=e.archive_target_check(self.root,e.CORE)
        self.assertFalse(core['ok'])
        profile=e.archive_target_check(self.root,self.root)
        self.assertFalse(profile['ok'])
        bad_child=e.archive_target_check(self.root,self.base/'parent','a/b')
        self.assertFalse(bad_child['ok'])

    def test_cli_status_and_mark(self):
        env=dict(os.environ,LOCALAPPDATA=str(self.base/'unbound'))
        command=[sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(self.root)]
        def run(*args):return subprocess.run(command+list(args),env=env,capture_output=True,encoding='utf-8')
        first=run('archive-status');self.assertEqual(first.returncode,0,first.stderr)
        self.assertFalse(json.loads(first.stdout)['due'])
        mark={'state':'advised','at':'2026-09-09T00:00:00Z'}
        mark_path=self.base/'mark.json';mark_path.write_text(json.dumps(mark),encoding='utf-8')
        marked=run('archive-mark',str(mark_path));self.assertEqual(marked.returncode,0,marked.stderr)
        self.assertEqual(json.loads(marked.stdout)['state'],'advised')
        again=run('archive-status');self.assertEqual(again.returncode,0,again.stderr)
        self.assertEqual(json.loads(again.stdout)['last_advised_state'],'advised')


if __name__=='__main__':
    unittest.main()
