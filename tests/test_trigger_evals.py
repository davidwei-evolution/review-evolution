"""Trigger-quality evals (D4, 2026-09-12).

The old suite covered core logic only: nothing asserted that a natural-language request
should or should not reach this skill. What is mechanically checkable here is the discovery
surface - the frontmatter description, the only text a host reads when deciding to load the
skill. These cases therefore assert that every phrasing we expect to match is present in
that description, and that negative cases are covered by an explicit boundary sentence.
They do NOT prove a host will fire; only a real session can show that.
"""
from pathlib import Path
import json,sys,unittest

CORE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CORE/'tests'))
from test_skill_metadata import read_frontmatter

CASES=json.loads((CORE/'tests'/'evals'/'trigger.json').read_text(encoding='utf-8'))

class TriggerEvals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.description=(read_frontmatter(CORE/'SKILL.md').get('description') or '').casefold()

    def test_eval_file_shape(self):
        self.assertEqual(1,CASES['schema'])
        ids=[case['id'] for case in CASES['cases']]
        self.assertEqual(len(ids),len(set(ids)),'duplicate case id')
        for case in CASES['cases']:
            self.assertIn('input',case)
            self.assertIn(case['should_trigger'],(True,False))

    def test_positive_cases_are_covered_by_the_description(self):
        missing=[]
        for case in CASES['cases']:
            if not case['should_trigger']:
                continue
            for term in case.get('expect_terms') or []:
                if term.casefold() not in self.description:
                    missing.append((case['id'],term))
        self.assertEqual([],missing,'触发词在 description 里找不到，宿主无法按该说法命中')

    def test_negative_cases_have_an_explicit_boundary(self):
        missing=[]
        for case in CASES['cases']:
            if case['should_trigger'] or not case.get('boundary'):
                continue
            if case['boundary'].casefold() not in self.description:
                missing.append((case['id'],case['boundary']))
        self.assertEqual([],missing,'负例缺少 description 里的边界句，容易被无关请求误触发')

    def test_english_search_terms_are_present(self):
        for term in ('retrospective','lessons learned','long-term memory','cross-device merge'):
            self.assertIn(term,self.description)

if __name__=='__main__':
    unittest.main()
