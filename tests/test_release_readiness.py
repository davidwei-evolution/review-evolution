"""Batch-4 regressions: D4 (real-shape fixtures + single-field injection), D8 (pack core_api
must match content), D11 (public release identity stays allowed), E3 (release-review triage)."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
import release_gate as gate
import safe_store as st
from test_components import record, event, test_review, optional_s3_enabled

# Fields a looser writer could plausibly add. Identity fields (component/id/state) are
# covered separately: a record-level injection of those is invalid, not redundant.
INJECT_RECORDS=('note','extra_field','source','confirmed_at','tags')
INJECT_EVENTS=('id','score','state','note','extra_field')

def realistic_profile(root):
    """A profile shaped the way real usage produces it: mixed states, a classified S2,
    a preference event written by a looser older writer, and a superseded record."""
    e.init(root)
    old=record(module='documents',text='先给结论',scope='work')
    e.add(root,old)
    e.add(root,record(module='documents',state='confirmed',confirmed_by='synthetic yes',
                      text='先给结论再展开理由',scope='work',supersedes=old['id']))
    e.add(root,record('s2',module='release',state='confirmed',confirmed_by='synthetic yes',
                      s2_type='execution',s2_applicability='reusable-method',
                      s2_context='仅在候选来源已核验时适用',text='导出前先计划再确认'))
    e.add(root,record('s2',module='release',text='未分类的候选经验'))
    e.add_event(root,event(source='sandbox:real-shape'))
    legacy=event(source='sandbox:legacy-shape',preference_id='legacy')
    legacy['component']='s1'
    st.atomic_bytes(root/'preferences'/'events'/(e.pe.event_id(legacy)+'.json'),
                    st.json_bytes(legacy))
    return root

class RealShapeFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=realistic_profile(self.base/'real')

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_shape_profile_exports_imports_and_stays_idempotent(self):
        for components in (['s1'],['s2'],['s1','s2']):
            with self.subTest(components=components):
                plan=e.export_plan(self.root,components)
                pack=self.base/('pack-'+''.join(components))
                e.export_pack(self.root,pack,components,plan_id=plan['plan_id'])
                man,rows=e.validate_pack(pack)
                self.assertTrue(rows)
                target=self.base/('target-'+''.join(components));e.init(target)
                preview=e.import_plan(target,pack,merge_into_current=True)
                first=e.import_pack(target,pack,preview['plan_id'],merge_into_current=True,
                                    trust_reason='synthetic real-shape merge')
                self.assertTrue(first['added'])
                again=e.import_plan(target,pack,merge_into_current=True)
                repeat=e.import_pack(target,pack,again['plan_id'],merge_into_current=True,
                                     trust_reason='synthetic real-shape merge')
                self.assertEqual(repeat.get('added',0),0)

    def test_single_field_injection_on_records_never_breaks_export(self):
        for field in INJECT_RECORDS:
            with self.subTest(field=field):
                row=record(module='injected',**{field:'synthetic-'+field})
                e.add(self.root,row)
                self.assertTrue(e.export_plan(self.root,['s1'])['files'])

    def test_single_field_injection_on_events_is_stripped_or_rejected(self):
        for field in INJECT_EVENTS:
            with self.subTest(field=field):
                row=event(source='sandbox:inject-'+field,preference_id='inject'+field.replace('_',''))
                row[field]='synthetic'
                result=e.add_event(self.root,row)
                self.assertIn(result['status'],('added','unchanged'))
                stored=json.loads((self.root/'preferences'/'events'/
                                   (result['event_id']+'.json')).read_text(encoding='utf-8'))
                self.assertNotIn(field,stored)
                self.assertTrue(e.export_plan(self.root,['s1'])['files'])

class PackCoreApiMatchesContent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def build_pack(self,components,core_api=None):
        plan=e.export_plan(self.root,components)
        pack=self.base/('pack-'+''.join(components))
        e.export_pack(self.root,pack,components,plan_id=plan['plan_id'])
        if core_api is not None:
            man=json.loads((pack/'pack.json').read_text(encoding='utf-8'))
            man['core_api']=core_api
            man.pop('pack_id')
            man['pack_id']=st.digest(e.encoded(man))
            (pack/'pack.json').write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n',
                                          encoding='utf-8')
        return pack

    def test_classified_export_declares_core_api_two(self):
        e.add(self.root,record('s2',s2_type='execution',s2_applicability='task-environment',
                               s2_context='synthetic'))
        pack=self.build_pack(['s2'])
        man,rows=e.validate_pack(pack)
        self.assertEqual(man['core_api'],2)
        self.assertTrue(any('s2_type' in r for r in rows.values()))

    def test_unclassified_export_still_declares_core_api_one(self):
        e.add(self.root,record('s2'))
        man,_=e.validate_pack(self.build_pack(['s2']))
        self.assertEqual(man['core_api'],1)

    def test_old_core_style_pack_is_rejected_with_an_actionable_message(self):
        e.add(self.root,record('s2',s2_type='execution',s2_applicability='task-environment',
                               s2_context='synthetic'))
        pack=self.build_pack(['s2'],core_api=1)
        with self.assertRaises(ValueError) as raised:
            e.validate_pack(pack)
        message=str(raised.exception)
        self.assertIn('core API 2',message)
        self.assertIn('re-export',message)

class PublicIdentityStaysAllowed(unittest.TestCase):
    def test_both_identities_are_registered(self):
        pairs={(name,lineage) for name,lineage,_ in gate.ALLOWED_IDENTITIES}
        self.assertIn(('wb-review-evolution','wb-review-evolution'),pairs)
        self.assertIn(('review-evolution','wb-review-evolution'),pairs)

    def test_public_identity_payload_passes_the_content_gate(self):
        data=gate.load_payload(e.CORE)
        meta=json.loads(data['CORE.json'])
        meta['canonical_name']='review-evolution'
        data['CORE.json']=st.json_bytes(meta)
        # 1.0 (2026-09-12): the shipped core is a stable release, so the gate additionally requires
        # the stable_evidence block. Supply a synthetic receipt instead of relaxing the gate.
        review=gate.draft(e.CORE)
        review['stable_evidence'].update(
            tests_evidence='Synthetic fixture reference',
            acceptance_evidence='Synthetic fixture reference; not publication approval',
            frozen_core_sha256=st.digest(data['CORE.json']),confirmations=2)
        report=gate.scan_payload(data,review)
        self.assertEqual(report['findings'],[])

class UpdateRelation(unittest.TestCase):
    """D10: '本机领先发布线' must not read as '有更新待装'."""

    def test_version_relation_three_states(self):
        pairs=(('0.22.4-beta.1','0.21.5-beta.1','local-ahead'),
               ('0.21.5-beta.1','0.22.4-beta.1','behind'),
               ('0.22.4-beta.1','0.22.4-beta.1','equal'),
               ('0.22.0-beta.1','0.22.0-beta.2','behind'))
        for installed,latest,expected in pairs:
            with self.subTest(installed=installed,latest=latest):
                self.assertEqual(e._version_ahead(installed,latest),expected)

class ReleaseReviewTriage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_defect_shaped_entries_are_listed_read_only(self):
        e.log_s3(self.root,{'task_id':'defect-a','text':'导出时崩溃，报错 ERROR: id',
                            'evidence':'synthetic'})
        e.log_s3(self.root,{'task_id':'defect-b','status':'in-core','text':'该崩溃已修复并入核心',
                            'evidence':'synthetic','review_reference':'synthetic review reference'})
        e.log_s3(self.root,{'task_id':'calm','text':'例行的版本发布说明','evidence':'synthetic'})
        before=e.profile_digest(self.root)
        result=e.release_review(self.root)
        self.assertEqual(result['defect_like'],2)
        self.assertEqual(result['not_in_core'],1)
        self.assertEqual(sorted(i['task_id'] for i in result['items']),['defect-a','defect-b'])
        self.assertEqual(e.profile_digest(self.root),before)
        self.assertTrue(result['read_only'])

# 027: release-review reads the S3 journal, which exists only with the optional S3 module.
if not optional_s3_enabled():
    setattr(ReleaseReviewTriage,'test_defect_shaped_entries_are_listed_read_only',
            (lambda self:self.skipTest('optional S3 module not installed in this edition')))
