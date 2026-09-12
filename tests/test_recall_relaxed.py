"""E1 regression: natural-language queries that miss on strict term matching must
fall back to weighted overlap once, and NO_MATCH must tell you what to try next."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
from recall_view import recall
from test_components import record

TEXT='改 SKILL.md 后必须同步已安装副本，并核对核心版本行一致'

class QueryUnits(unittest.TestCase):
    def test_ascii_words_pass_through(self):
        self.assertEqual(e.query_units('SKILL release'),['skill','release'])

    def test_cjk_becomes_bigrams(self):
        self.assertEqual(e.query_units('技能进化'),['技能','能进','进化'])

    def test_single_cjk_character_is_kept(self):
        self.assertIn('门',e.query_units('门'))

    def test_overlap_score_bounds(self):
        self.assertEqual(e.overlap_score(TEXT,TEXT),1.0)
        self.assertEqual(e.overlap_score(TEXT,'完全无关的说法'),0.0)
        self.assertGreater(e.overlap_score(TEXT,'SKILL 同步 升级'),0.5)

class RelaxedFallback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)
        e.add(self.root,record(state='confirmed',confirmed_by='synthetic yes',text=TEXT))

    def tearDown(self):
        self.tmp.cleanup()

    def test_natural_language_query_falls_back_and_is_marked(self):
        q=e.query(self.root,text='SKILL 同步 升级')
        self.assertTrue(q['records'],'relaxed fallback should find the related record')
        self.assertEqual(q.get('text_match'),'relaxed')
        self.assertIn('相关性',q.get('text_match_note',''))

    def test_strict_query_is_not_marked_relaxed(self):
        q=e.query(self.root,text='已安装副本')
        self.assertTrue(q['records'])
        self.assertNotIn('text_match',q)

    def test_unrelated_query_still_returns_nothing(self):
        q=e.query(self.root,text='气象 台风 路径')
        self.assertFalse(q['records'])

    def test_recall_surfaces_the_relaxed_marker(self):
        result=recall(self.root,component='s1',text='SKILL 同步 升级')
        self.assertEqual(result['status'],'OK')
        self.assertTrue(result['items'])

    def test_no_match_lists_modules_to_try(self):
        for module in ('documents','release'):
            e.add(self.root,record(module=module,text='占位经验 '+module))
        result=recall(self.root,component='s1',text='气象 台风 路径')
        self.assertEqual(result['status'],'NO_MATCH')
        diagnosis=result['diagnosis']
        self.assertEqual(diagnosis['code'],'LEXICAL_NO_MATCH')
        self.assertIn('documents',diagnosis['modules'])
        self.assertIn('module',diagnosis['retry'])
