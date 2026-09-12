"""Candidate-confirm reminder: visibility, thresholds, cooldown, decline and disable."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
from test_components import record

def candidates(profile,n,tag='cand'):
    for i in range(n):
        e.add(profile,record(text=f'{tag}-{i}'))

class CandidateReminder(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_is_read_only_and_counts_by_state(self):
        candidates(self.root,3)
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic yes'))
        before=e.profile_digest(self.root)
        status=e.candidate_status(self.root)
        self.assertTrue(status['read_only'])
        self.assertEqual(status['counts']['candidate'],3)
        self.assertEqual(status['counts']['confirmed'],1)
        self.assertEqual(e.profile_digest(self.root),before)

    def test_first_reminder_needs_the_threshold(self):
        candidates(self.root,9)
        self.assertFalse(e.candidate_status(self.root)['due'])
        e.add(self.root,record(text='第十条候选'))
        status=e.candidate_status(self.root)
        self.assertTrue(status['due'])
        self.assertEqual([r['condition'] for r in status['reasons']],['A'])

    def test_advising_then_declining_silences_for_the_interval(self):
        candidates(self.root,10)
        e.candidate_mark(self.root,{'state':'advised'})
        self.assertFalse(e.candidate_status(self.root)['due'])
        e.candidate_mark(self.root,{'state':'declined'})
        status=e.candidate_status(self.root)
        self.assertFalse(status['due'])
        self.assertEqual(status['last_advised_state'],'declined')

    def test_ratio_condition_C_fires_for_a_lopsided_archive(self):
        candidates(self.root,6)
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic yes'))
        e.candidate_mark(self.root,{'state':'advised','at':'2020-01-01T00:00:00+00:00'})
        status=e.candidate_status(self.root)
        self.assertTrue(status['due'])
        self.assertEqual([r['condition'] for r in status['reasons']],['C'])

    def test_condition_B_after_the_interval(self):
        candidates(self.root,12)
        e.candidate_mark(self.root,{'state':'advised','at':'2020-01-01T00:00:00+00:00'})
        conditions=[r['condition'] for r in e.candidate_status(self.root)['reasons']]
        self.assertIn('B',conditions)

    def test_disabled_reminder_reports_no_due(self):
        candidates(self.root,20)
        e.candidate_mark(self.root,{'state':'advised','enabled':False})
        status=e.candidate_status(self.root)
        self.assertFalse(status['due'])
        self.assertIn('disabled',status['note'])

    def test_confirm_mark_records_a_baseline(self):
        candidates(self.root,10)
        result=e.candidate_mark(self.root,{'state':'confirmed'})
        self.assertEqual(result['marked'],'confirmed')
        state=e.load_candidate_state(self.root)
        self.assertEqual(state['baseline']['candidates'],10)
        self.assertIsNotNone(state['last_confirmed_at'])

    def test_mark_rejects_bad_state_and_values(self):
        with self.assertRaises(ValueError):
            e.candidate_mark(self.root,{'state':'done'})
        with self.assertRaises(ValueError):
            e.candidate_mark(self.root,{'state':'advised','interval_days':'soon'})
        with self.assertRaises(ValueError):
            e.candidate_mark(self.root,{'state':'advised','at':'2026-09-11'})

    def test_confirming_reduces_the_candidate_count(self):
        candidates(self.root,10)
        ids=[r['id'] for r in e.query(self.root)['records']]
        plan=e.candidate_confirm_plan(self.root,ids)
        e.confirm_candidates(self.root,ids,plan['plan_id'],'synthetic confirmation')
        counts=e.candidate_status(self.root)['counts']
        self.assertEqual(counts['candidate'],0)
        self.assertEqual(counts['confirmed'],10)
        self.assertEqual(counts['s1_candidate'],0)

    def test_retiring_a_duplicate_removes_it_from_candidates(self):
        first=record(text='重复的经验');second=record(text='重复的经验')
        e.add(self.root,first);e.add(self.root,second)
        e.add(self.root,record(text='停用重复条目：整合到前一条',state='retired',
                               supersedes=second['id']))
        counts=e.candidate_status(self.root)['counts']
        self.assertEqual(counts['candidate'],1)
        # 两条处于 retired：停用标记本身 + 被停用的原候选（标记不删原记录）
        self.assertEqual(counts['retired'],2)
