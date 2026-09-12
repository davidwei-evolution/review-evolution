"""P10: candidates are surfaced only when nothing confirmed matches, and only as
clearly-marked fallback; plus the batch-confirm entry that turns candidates into rules."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
import safe_store as st
from recall_view import recall
from test_components import record

class CandidateFallback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_candidate_is_returned_only_as_marked_fallback(self):
        e.add(self.root,record(text='只给结论不要过程'))
        result=recall(self.root,component='s1',text='结论')
        self.assertEqual(result['status'],'OK')
        self.assertTrue(result['items'])
        self.assertTrue(result['candidate_fallback'])
        self.assertIn('未确认',result['candidate_note'])
        self.assertEqual(result['items'][0]['kind'],'candidate-not-rule')

    def test_confirmed_hit_suppresses_the_candidate_fallback(self):
        e.add(self.root,record(text='先给结论再展开',state='confirmed',confirmed_by='synthetic yes'))
        e.add(self.root,record(text='结论后直接结束'))
        result=recall(self.root,component='s1',text='结论')
        self.assertEqual(result['status'],'OK')
        self.assertNotIn('candidate_fallback',result)
        self.assertTrue(all(i['kind']!='candidate-not-rule' for i in result['items']))

    def test_unrelated_text_still_reports_no_match(self):
        e.add(self.root,record(text='只给结论不要过程'))
        result=recall(self.root,component='s1',text='气象 台风')
        self.assertEqual(result['status'],'NO_MATCH')
        self.assertNotIn('candidate_fallback',result)

    def test_explicit_candidate_request_is_not_marked_as_fallback(self):
        e.add(self.root,record(text='只给结论不要过程'))
        result=recall(self.root,component='s1',text='结论',include_candidates=True)
        self.assertTrue(result['items'])
        self.assertNotIn('candidate_fallback',result)

class BatchConfirm(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)
        self.first=record(text='批量确认样例一')
        self.second=record('s2',text='批量确认样例二')
        e.add(self.root,self.first);e.add(self.root,self.second)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_is_read_only_and_explicit(self):
        before=e.profile_digest(self.root)
        plan=e.candidate_confirm_plan(self.root,[self.first['id']])
        self.assertEqual(plan['count'],1)
        self.assertEqual(plan['items'][0]['id'],self.first['id'])
        self.assertNotEqual(plan['items'][0]['new_id'],self.first['id'])
        self.assertEqual(e.profile_digest(self.root),before)

    def test_confirm_creates_a_confirmed_revision_and_keeps_the_original(self):
        plan=e.candidate_confirm_plan(self.root,[self.first['id'],self.second['id']])
        result=e.confirm_candidates(self.root,[self.first['id'],self.second['id']],
                                    plan['plan_id'],'synthetic confirmation')
        self.assertEqual(result['status'],'confirmed')
        self.assertEqual(result['confirmed'],2)
        rows=e.query(self.root)['records']
        by_id={r['id']:r for r in rows}
        for source in (self.first,self.second):
            new_id=st.digest(e.encoded({'confirm-candidate':source['id']}))[:32]
            self.assertEqual(by_id[new_id]['effective_state'],'confirmed')
            self.assertEqual(by_id[new_id]['supersedes'],source['id'])
            self.assertEqual(by_id[source['id']]['effective_state'],'superseded')

    def test_stale_plan_and_missing_confirmation_are_rejected(self):
        plan=e.candidate_confirm_plan(self.root,None,component='s1')
        with self.assertRaises(ValueError):
            e.confirm_candidates(self.root,None,plan['plan_id'],'')
        with self.assertRaises(ValueError):
            e.confirm_candidates(self.root,None,'0'*64,'synthetic confirmation',component='s1')
        e.confirm_candidates(self.root,None,plan['plan_id'],'synthetic confirmation',component='s1')
        with self.assertRaises(ValueError):
            e.confirm_candidates(self.root,None,plan['plan_id'],'synthetic confirmation',component='s1')

    def test_unknown_or_already_confirmed_id_is_rejected(self):
        with self.assertRaises(ValueError):
            e.candidate_confirm_plan(self.root,['f'*32])

    def test_already_superseded_record_is_not_offered_again(self):
        stale=record(text='旧候选')
        e.add(self.root,stale)
        e.add(self.root,record(text='旧候选',state='confirmed',confirmed_by='synthetic yes',
                               supersedes=stale['id']))
        planned={item['id'] for item in e.candidate_confirm_plan(self.root,None)['items']}
        self.assertNotIn(stale['id'],planned)
        self.assertEqual(planned,{self.first['id'],self.second['id']})
        with self.assertRaises(ValueError):
            e.candidate_confirm_plan(self.root,[stale['id']])
