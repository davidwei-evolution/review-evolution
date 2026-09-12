from pathlib import Path
import json,os,sys,tempfile,unittest,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e
import safe_store as st
import recall_view as cw
import profile_backup as pb
from test_components import record,event,s1outcome


class RecallView(unittest.TestCase):
    def test_mixed_equal_rank_keeps_s2_with_small_budget(self):
        for i in range(9):
            e.add_event(self.root,event(source='synthetic:'+str(i),preference_id='pref'+str(i)))
        lesson=record('s2',state='confirmed',confirmed_by='synthetic')
        e.add(self.root,lesson)
        before=self.snapshot()
        result=cw.recall(self.root,scope='work',module='documents',limit=2)
        self.assertIn(lesson['id'],[r['id'] for r in result['items']])
        self.assertEqual(len(result['items']),2)
        self.assertEqual(result['omitted'],8)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(result,cw.recall(self.root,scope='work',module='documents',limit=2))

    def test_mixed_budget_does_not_promote_candidate_or_weaker_match(self):
        for i in range(3):
            e.add_event(self.root,event(source='synthetic:'+str(i),preference_id='pref'+str(i)))
        candidate=record('s2');e.add(self.root,candidate)
        general=record('s2',state='confirmed',confirmed_by='synthetic',scope='general',module='other')
        e.add(self.root,general)
        result=cw.recall(self.root,scope='work',module='documents',limit=2,include_candidates=True)
        self.assertTrue(all(r['kind']=='effective-preference' for r in result['items']))
        only=cw.recall(self.root,component='s2',scope='work',module='documents',include_candidates=True)
        self.assertEqual({r['id'] for r in only['items']},{candidate['id'],general['id']})

    def test_specific_experience_survives_general_preference_budget(self):
        for i in range(10):
            e.add_event(self.root,event(source='synthetic:'+str(i),preference_id='pref'+str(i),scope='general'))
        row=record(state='confirmed',confirmed_by='synthetic',module='documents',text='Task specific')
        e.add(self.root,row)
        result=cw.recall(self.root,scope='work',module='documents',limit=1)
        self.assertEqual(result['items'][0]['id'],row['id'])
        self.assertEqual(result['status'],'TRUNCATED')
    def test_cli_exact_character_budget_and_oversized_rule(self):
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic',text='长经验'*900+'重要例外'))
        cmd=[sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(self.root),'recall','--max-chars','1200']
        result=subprocess.run(cmd,capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertLessEqual(len(result.stdout),1200)
        value=json.loads(result.stdout)
        self.assertEqual(value['status'],'TRUNCATED');self.assertEqual(value['omitted'],1)
        self.assertEqual(value['items'],[])
        failed=subprocess.run(cmd[:-1]+['2'],capture_output=True,encoding='utf-8')
        self.assertNotEqual(failed.returncode,0);self.assertEqual(failed.stdout,'')

    def test_s2_conditions_and_component_filter_preserved(self):
        lesson=record('s2',state='confirmed',confirmed_by='synthetic',text='Synthetic fix')
        e.add(self.root,lesson);e.add(self.root,record(state='confirmed',confirmed_by='synthetic'))
        result=cw.recall(self.root,component='s2');item=result['items'][0]
        self.assertEqual(len(result['items']),1)
        for field in ('cause','prevention','counter_signal'):
            self.assertEqual(item[field],lesson[field])
        self.assertIn('environment_review',item)

    def test_pending_only_and_independent_profile(self):
        e.add_event(self.root,event(kind='support',classification_state='staged'))
        result=cw.recall(self.root)
        self.assertEqual(result['status'],'PENDING_ONLY');self.assertGreater(result['pending_count'],0)
        other=self.base/'other';e.init(other)
        other_result=cw.recall(other)
        self.assertEqual(other_result['status'],'NO_MATCH')
        self.assertNotEqual(result['profile_id'],other_result['profile_id'])

    def test_limit_retains_whole_records_and_read_failure_is_not_empty(self):
        for i in range(3):e.add(self.root,record(state='confirmed',confirmed_by='synthetic',text='Synthetic '+str(i)))
        result=cw.recall(self.root,limit=1)
        self.assertEqual(len(result['items']),1);self.assertEqual(result['omitted'],2)
        self.assertEqual(result['status'],'TRUNCATED')
        with patch.object(e,'query',side_effect=PermissionError('synthetic')):
            with self.assertRaises(PermissionError):cw.recall(self.root)
    def snapshot(self):return pb.inventory(self.root)[0]
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)


    def tearDown(self):self.tmp.cleanup()


    def test_recall_excludes_inactive_and_candidates_unless_requested(self):
        old=record(state='confirmed',confirmed_by='synthetic');e.add(self.root,old)
        e.add(self.root,record(state='retired',supersedes=old['id']))
        candidate=record();e.add(self.root,candidate)
        good=record(state='confirmed',confirmed_by='synthetic',text='Keep all qualifications');e.add(self.root,good)
        rows=cw.recall(self.root)['items']
        self.assertEqual([r['id'] for r in rows],[good['id']])
        rows=cw.recall(self.root,include_candidates=True)['items']
        self.assertIn('candidate-not-rule',[r['kind'] for r in rows])


    def test_recall_scope_budget_and_complete_qualifications(self):
        e.add_event(self.root,event())
        e.add(self.root,record(state='confirmed',confirmed_by='yes',scope='personal',text='private other scope'))
        e.add(self.root,record(state='confirmed',confirmed_by='yes',text='x'*6000+' important exception'))
        before=self.snapshot();result=cw.recall(self.root,scope='work',max_chars=1500)
        self.assertEqual(result['status'],'TRUNCATED')
        self.assertLessEqual(len(cw.serialize(result))+1,1500)
        self.assertNotIn('private other scope',str(result));self.assertNotIn('xxxx',str(result))
        self.assertEqual(before,self.snapshot())


    def test_recall_no_match_and_failure_are_distinct(self):
        self.assertEqual(cw.recall(self.root,text='absent')['status'],'NO_MATCH')
        with patch.object(e,'query',side_effect=ValueError('changed')):
            with self.assertRaises(ValueError):cw.recall(self.root)
        with self.assertRaises(ValueError):cw.recall(self.root,max_chars=10)


    def test_new_process_recall_after_correction(self):
        old=record(state='confirmed',confirmed_by='synthetic',text='Old choice');e.add(self.root,old)
        new=record(state='confirmed',confirmed_by='synthetic',text='New choice',supersedes=old['id']);e.add(self.root,new)
        result=subprocess.run([sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(self.root),'recall'],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([r['id'] for r in json.loads(result.stdout)['items']],[new['id']])

    def test_no_match_diagnosis_empty_and_candidates_only(self):
        empty=cw.recall(self.root,text='absent')
        self.assertEqual(empty['status'],'NO_MATCH')
        self.assertEqual(empty['diagnosis']['code'],'EMPTY_PROFILE')
        e.add(self.root,record())
        only=cw.recall(self.root)
        # P10 (v0.22.5): 只有候选时不再报 NO_MATCH，而是兜底返回并明确标注未确认。
        self.assertEqual(only['status'],'OK')
        self.assertTrue(only['candidate_fallback'])
        self.assertEqual(only['items'][0]['kind'],'candidate-not-rule')
        self.assertIn('未确认',only['candidate_note'])

    def test_no_match_diagnosis_scope_and_lexical(self):
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic',
                               scope='work',module='documents',text='工作区中文经验'))
        scoped=cw.recall(self.root,scope='personal',text='工作区中文经验')
        self.assertEqual(scoped['status'],'NO_MATCH')
        self.assertEqual(scoped['diagnosis']['code'],'SCOPE_FILTERED')
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic',
                               scope='general',module='documents',text='中文经验关键词'))
        lexical=cw.recall(self.root,scope='general',module='documents',text='苹果',fuzzy=False)
        self.assertEqual(lexical['status'],'NO_MATCH')
        self.assertEqual(lexical['diagnosis']['code'],'LEXICAL_NO_MATCH')
        self.assertIn('--fuzzy',lexical['diagnosis']['retry'])

