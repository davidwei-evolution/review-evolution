"""Guard the release-check rule that the core version, the README header line and the
SKILL title line always agree (they drifted silently before)."""
from pathlib import Path
import json,sys,unittest
CORE=Path(__file__).resolve().parents[1]

class DocsVersionConsistency(unittest.TestCase):
    def setUp(self):
        self.version=json.loads((CORE/'CORE.json').read_text(encoding='utf-8'))['version']

    def test_readme_header_reports_the_core_version(self):
        header=(CORE/'README.md').read_text(encoding='utf-8').splitlines()[0]
        self.assertTrue(header.startswith('# '),header)
        self.assertIn(self.version,header)

    def test_skill_title_reports_the_core_version(self):
        title=next(line for line in (CORE/'SKILL.md').read_text(encoding='utf-8').splitlines()
                   if line.startswith('# Review Evolution'))
        self.assertIn(self.version,title)

    def test_changelog_leads_with_the_core_version(self):
        text=(CORE/'CHANGELOG.md').read_text(encoding='utf-8')
        public=json.loads((CORE/'CORE.json').read_text(encoding='utf-8'))['canonical_name']=='review-evolution'
        if public:
            self.assertTrue(text.startswith('# 更新说明'))
            self.assertIn(self.version,text)
        else:
            self.assertIn(self.version,text.splitlines()[0])
