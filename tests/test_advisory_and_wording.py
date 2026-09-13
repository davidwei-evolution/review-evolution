"""2026-09-13：宿主规则提示（首次/抱怨/90 天）+ 真机反馈 F1/F3 的口径护栏。"""
from pathlib import Path
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / 'scripts'))
import experience as e          # noqa: E402
import diagnostics as diag      # noqa: E402


class HostRuleAdvisory(unittest.TestCase):
    """提示与记账只落在安装级状态，不进私人档案、不随经验包转移。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / 'local'
        self.home.mkdir()
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_first_run_is_due_then_marked_not_due(self):
        first = e.host_rule_status()
        self.assertTrue(first['due'])
        self.assertIsNone(first['last_advised_at'])
        self.assertIn('review-evolution', first['rule_text'])
        e.mark_host_rule({'state': 'advised', 'placed_where': 'AGENTS.md'})
        after = e.host_rule_status()
        self.assertFalse(after['due'])
        self.assertEqual(after['advised_count'], 1)
        self.assertEqual(after['placed_where'], 'AGENTS.md')
        self.assertEqual(after['interval_days'], 90)

    def test_due_again_after_the_interval_and_decline_is_recorded(self):
        e.mark_host_rule({'state': 'declined'})
        self.assertFalse(e.host_rule_status()['due'])
        self.assertTrue(e.host_rule_status()['declined'])
        old = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(days=e.HOST_RULE_INTERVAL_DAYS + 1)).isoformat(timespec='seconds')
        state = e.load_host_rule_state()
        state['last_advised_at'] = old
        e.host_rule_path().write_bytes(e.st.json_bytes(state))
        self.assertTrue(e.host_rule_status()['due'])

    def test_state_lives_in_the_installation_area_not_in_the_profile(self):
        profile = Path(self.tmp.name) / 'profile'
        e.init(profile)
        e.mark_host_rule({'state': 'advised'})
        self.assertTrue(e.host_rule_path().is_file())
        self.assertTrue(e.host_rule_path().is_relative_to(self.home))
        self.assertFalse(any('host-rule' in p.name for p in profile.rglob('*')))

    def test_intro_carries_the_advisory_only_when_due(self):
        profile = Path(self.tmp.name) / 'profile2'
        e.init(profile)
        before = e.introduction(profile=profile)
        self.assertIn('host_rule', before)
        self.assertIn('host-rule', [c['id'] for c in before['capabilities']])
        e.mark_host_rule({'state': 'advised'})
        after = e.introduction(profile=profile)
        self.assertNotIn('host_rule', after)
        self.assertNotIn('host-rule', [c['id'] for c in after['capabilities']])


class WordingGuards(unittest.TestCase):
    """F1：triggered 与 proposal 语义不同，必须给出可直接读懂的口径。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'profile'
        e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, module):
        return dict(id=os.urandom(16).hex(), component='s1', module=module, scope='work',
                    category='writing', state='candidate', text='Synthetic', task_id='t-' + module,
                    created_at='2026-01-01T00:00:00Z', evidence=['synthetic'])

    def test_threshold_reached_is_explained_even_without_a_proposal(self):
        # 用彼此不相似的标签，确保命中"已达阈值但无可归并项"这一真实场景。
        for i in range(3):
            e.add(self.root, self._record(('alpha-report', 'beta-slides', 'gamma-sheet')[i]))
        census = e.scene_census(self.root, threshold=2)
        self.assertTrue(census['triggered'])
        self.assertEqual(census['threshold_reached'], census['triggered'])
        self.assertEqual(census['proposal'], [])
        self.assertIn('无需归并', census['proposal_note'])
        self.assertIn('不等于', census['triggered_means'])

    def test_below_threshold_says_so(self):
        e.add(self.root, self._record('only-one'))
        census = e.scene_census(self.root, threshold=8)
        self.assertFalse(census['triggered'])
        self.assertIn('未达阈值', census['proposal_note'])


class MultiInstallAdvice(unittest.TestCase):
    """F3：多份安装版本不一致时，处置建议必须出现在顶层 next_step。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'profile'
        e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_version_mismatch_is_promoted_to_next_step(self):
        installs = {'count': 2, 'read_only': True, 'installs': [],
                    'version_mismatch': ['1.0.0', '1.1.7']}
        with patch.object(diag, 'other_installations', return_value=installs):
            report = diag.doctor(self.root)
        self.assertEqual(report['status'], 'OK')
        self.assertIn('版本不一致', report['next_step'])
        self.assertIn('统一升级或移除重复安装', report['next_step'])

    def test_single_install_keeps_the_plain_next_step(self):
        installs = {'count': 1, 'read_only': True, 'installs': []}
        with patch.object(diag, 'other_installations', return_value=installs):
            report = diag.doctor(self.root)
        self.assertNotIn('版本不一致', report['next_step'])


if __name__ == '__main__':
    unittest.main()
