"""Guard the skill's discovery surface.

The frontmatter description is the only text a host reads when deciding whether to load
this skill, so two failures must not come back: (1) the development copy sat 14 characters
below the 1024-character host limit, and (2) the public candidate shipped a different,
hand-written description that had lost every trigger word. Both were found on 2026-09-12
while reviewing a real install on another client.
"""
from pathlib import Path
import sys,unittest

CORE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CORE/'scripts'))

# Hard limit enforced by the Codex/Anthropic skill validator (quick_validate.py).
HOST_LIMIT=1024
# Self-imposed margin: ordinary edits must not be able to cross the hard limit unnoticed.
SOFT_LIMIT=800
REQUIRED_CN=('经验复盘','收尾复盘','自我迭代','技能进化','理解用户习惯','个性化','长期记忆',
             '习惯校准','减少重复追问','跨设备/跨客户端经验整合')
REQUIRED_EN=('retrospective','reflection','lessons learned','self-iteration',
             'understand user habits','personalization','long-term memory',
             'habit calibration','cross-device merge')

def read_frontmatter(path):
    """Minimal dependency-free reader for the name/description block scalar."""
    lines=Path(path).read_text(encoding='utf-8').splitlines()
    if not lines or lines[0].strip()!='---':
        raise AssertionError('SKILL.md has no frontmatter')
    fields={};key=None
    for line in lines[1:]:
        if line.strip()=='---':
            break
        if key is not None:
            if line.strip() and not line.startswith((' ','\t')):
                key=None
            else:
                fields[key].append(line);continue
        if ':' not in line:
            continue
        name,value=line.split(':',1)
        value=value.strip()
        fields[name.strip()]=[] if value in ('>','>-','|','|-') else [value]
        key=name.strip()
    return {k:' '.join(part.strip() for part in v if part.strip()) for k,v in fields.items()}

class SkillMetadata(unittest.TestCase):
    def setUp(self):
        self.front=read_frontmatter(CORE/'SKILL.md')
        self.description=self.front.get('description','')

    def test_description_is_present(self):
        self.assertTrue(self.description)

    def test_description_stays_inside_the_host_limit(self):
        self.assertLessEqual(len(self.description),SOFT_LIMIT,
                             'description is '+str(len(self.description))+' characters; keep a margin '
                             'below the host limit of '+str(HOST_LIMIT))
        self.assertLessEqual(len(self.description),HOST_LIMIT)

    def test_description_has_no_angle_brackets(self):
        self.assertNotIn('<',self.description)
        self.assertNotIn('>',self.description)

    def test_description_keeps_chinese_trigger_words(self):
        missing=[word for word in REQUIRED_CN if word not in self.description]
        self.assertEqual([],missing,'trigger words lost from the description')

    def test_description_keeps_english_search_tags(self):
        lowered=self.description.casefold()
        missing=[word for word in REQUIRED_EN if word not in lowered]
        self.assertEqual([],missing,'English search tags lost from the description')

    def test_name_is_hyphen_case(self):
        name=self.front.get('name','')
        self.assertRegex(name,r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

    def test_public_candidate_reuses_the_development_description(self):
        """A public candidate must not carry a second, divergent description."""
        try:
            import build_public
        except ImportError:
            self.skipTest('public candidate: build_public.py is not shipped')
        self.assertEqual(build_public.skill_description(CORE),self.description)

if __name__=='__main__':
    unittest.main()
