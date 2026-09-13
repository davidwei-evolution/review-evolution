"""2026-09-13 用户规则：跨端合并不得用导入的记录覆盖本端已有条目的状态或内容。

期望行为：把会改变本端状态的那些 incoming 文件**扣下**（不应用），其余照常整合，
并在结果里**一次性**给出差异清单；用户确认后用 accept_state_changes 放行再应用。
补充口径（同日）：两端**内容**不一样（同 ID 不同内容）时同样扣下、不中断整包导入。
"""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / 'scripts'))
import experience as e          # noqa: E402
import safe_store as st         # noqa: E402


class MergeKeepsLocalState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'local')})
        self.env.start()
        self.target = root / 'target'
        self.source = root / 'source'
        e.init(self.target)
        e.init(self.source)
        self.record = {'id': 'a' * 32, 'component': 's1', 'module': 'documents', 'scope': 'work',
                       'category': 'writing', 'state': 'confirmed',
                       'confirmed_by': 'synthetic fixture', 'text': '合成偏好：交付后给链接与路径',
                       'task_id': 'merge-fixture', 'created_at': '2026-09-13T00:00:00Z',
                       'evidence': ['synthetic']}
        e.add(self.target, dict(self.record))
        e.add(self.source, dict(self.record))
        # 来源端把它停用（写一条 retired 标记，supersedes 指向该记录）
        e.add(self.source, {'id': 'b' * 32, 'component': 's1', 'module': 'documents',
                            'scope': 'work', 'category': 'writing', 'state': 'retired',
                            'supersedes': 'a' * 32, 'text': '停用上一条合成偏好',
                            'task_id': 'merge-fixture-retire',
                            'created_at': '2026-09-13T01:00:00Z', 'evidence': ['synthetic retire']})
        plan = e.export_plan(self.source, ['s1'])
        self.pack = Path(self.tmp.name) / 'pack'
        e.export_pack(self.source, self.pack, ['s1'], plan_id=plan['plan_id'])

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def state_of(self, profile, rid):
        rows = e.load_rows(profile)
        return e.effective_states({r['id']: r for r in rows.values()}).get(rid)

    def test_marker_is_held_and_reported_instead_of_applied(self):
        plan = e.import_plan(self.target, self.pack, merge_into_current=True)
        self.assertEqual([d['key'] for d in plan['discrepancies']], ['a' * 32])
        entry = plan['discrepancies'][0]
        self.assertEqual(entry['reason'], 'state-change')
        self.assertEqual(entry['local']['state'], 'confirmed')
        self.assertEqual(entry['merged_state'], 'retired')
        self.assertEqual(entry['source']['state'], 'retired')
        self.assertEqual(entry['held_files'], ['s1/records/' + 'b' * 32 + '.json'])
        self.assertNotIn('s1/records/' + 'b' * 32 + '.json', plan['add'])
        self.assertEqual(plan['hold'], ['s1/records/' + 'b' * 32 + '.json'])

        result = e.import_pack(self.target, self.pack, plan['plan_id'],
                               merge_into_current=True, trust_reason='synthetic ownership')
        self.assertEqual(result['discrepancies'][0]['key'], 'a' * 32)
        self.assertEqual(result['held'], ['s1/records/' + 'b' * 32 + '.json'])
        self.assertEqual(self.state_of(self.target, 'a' * 32), 'confirmed')

    def test_user_can_accept_the_change_and_then_it_applies(self):
        plan = e.import_plan(self.target, self.pack, merge_into_current=True,
                             accept_state_changes=['a' * 32])
        self.assertEqual(plan['discrepancies'], [])
        self.assertEqual(plan['hold'], [])
        self.assertIn('s1/records/' + 'b' * 32 + '.json', plan['add'])
        e.import_pack(self.target, self.pack, plan['plan_id'], merge_into_current=True,
                      trust_reason='synthetic ownership', accept_state_changes=['a' * 32])
        self.assertEqual(self.state_of(self.target, 'a' * 32), 'retired')

    def test_plan_id_binds_the_accept_set(self):
        plain = e.import_plan(self.target, self.pack, merge_into_current=True)
        accepted = e.import_plan(self.target, self.pack, merge_into_current=True,
                                 accept_state_changes=['a' * 32])
        self.assertNotEqual(plain['plan_id'], accepted['plan_id'])
        with self.assertRaises(ValueError):
            e.import_pack(self.target, self.pack, accepted['plan_id'],
                          merge_into_current=True, trust_reason='synthetic ownership')


class MergeKeepsLocalContent(unittest.TestCase):
    """同一 ID 在两端**内容**不一样：不覆盖本机、不中断整包，整合完再一次性列出差异。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'local')})
        self.env.start()
        self.target = root / 'target'
        self.source = root / 'source'
        e.init(self.target)
        e.init(self.source, e.info(self.target)['profile_id'])
        self.shared = {'id': 'c' * 32, 'component': 's1', 'module': 'documents', 'scope': 'work',
                       'category': 'writing', 'state': 'confirmed', 'confirmed_by': 'synthetic fixture',
                       'task_id': 'merge-content', 'created_at': '2026-09-13T00:00:00Z',
                       'evidence': ['synthetic']}
        self.only_source = {'id': 'd' * 32, 'component': 's1', 'module': 'documents', 'scope': 'work',
                            'category': 'writing', 'state': 'confirmed', 'confirmed_by': 'synthetic fixture',
                            'text': '来源独有、两端无争议的一条', 'task_id': 'merge-content-only',
                            'created_at': '2026-09-13T01:00:00Z', 'evidence': ['synthetic']}
        e.add(self.target, dict(self.shared, text='本机版本'))
        e.add(self.source, dict(self.shared, text='对方版本'))
        e.add(self.source, dict(self.only_source))
        plan = e.export_plan(self.source, ['s1'])
        self.pack = Path(self.tmp.name) / 'pack'
        e.export_pack(self.source, self.pack, ['s1'], plan_id=plan['plan_id'])

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def text_of(self, profile, rid):
        return e.load_rows(profile)['s1/records/' + rid + '.json']['text']

    def test_conflict_is_held_but_clean_records_still_import(self):
        plan = e.import_plan(self.target, self.pack)
        self.assertTrue(plan['conflicts'])
        self.assertEqual([d['kind'] for d in plan['discrepancies']], ['content'])
        self.assertEqual(plan['discrepancies'][0]['key'], 'c' * 32)
        self.assertEqual(plan['discrepancies'][0]['reason'], 'content-differs')
        self.assertEqual(plan['discrepancies'][0]['file'], 's1/records/' + 'c' * 32 + '.json')
        self.assertEqual(plan['discrepancies'][0]['local']['text'], '本机版本')
        self.assertEqual(plan['discrepancies'][0]['source']['text'], '对方版本')
        self.assertEqual(plan['hold'], ['s1/records/' + 'c' * 32 + '.json'])
        self.assertEqual(plan['overwrite'], [])
        self.assertNotIn('s1/records/' + 'c' * 32 + '.json', plan['add'])
        self.assertIn('s1/records/' + 'd' * 32 + '.json', plan['add'])

        result = e.import_pack(self.target, self.pack, plan['plan_id'])
        self.assertEqual(result['status'], 'imported')
        self.assertEqual(result['added'], 1)
        self.assertEqual([d['kind'] for d in result['discrepancies']], ['content'])
        # 无争议的那条已经整合进来；有争议的这条本机内容原封不动
        self.assertIn('s1/records/' + 'd' * 32 + '.json', e.load_rows(self.target))
        self.assertEqual(self.text_of(self.target, 'c' * 32), '本机版本')

    def test_accepting_source_content_overwrites_local(self):
        plan = e.import_plan(self.target, self.pack, accept_state_changes=['c' * 32])
        self.assertEqual(plan['discrepancies'], [])
        self.assertEqual(plan['hold'], [])
        self.assertEqual(plan['overwrite'], ['s1/records/' + 'c' * 32 + '.json'])
        result = e.import_pack(self.target, self.pack, plan['plan_id'],
                               accept_state_changes=['c' * 32])
        self.assertEqual(result['status'], 'imported')
        self.assertEqual(result['updated'], 1)
        self.assertEqual(self.text_of(self.target, 'c' * 32), '对方版本')

    def test_old_plan_without_the_accept_set_is_refused(self):
        plain = e.import_plan(self.target, self.pack)
        accepted = e.import_plan(self.target, self.pack, accept_state_changes=['c' * 32])
        self.assertNotEqual(plain['plan_id'], accepted['plan_id'])
        with self.assertRaises(ValueError):
            e.import_pack(self.target, self.pack, accepted['plan_id'])


if __name__ == '__main__':
    unittest.main()
