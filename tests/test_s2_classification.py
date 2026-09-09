from pathlib import Path
import sys,tempfile,unittest,subprocess,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e,recall_view as rv,profile_backup as pb,safe_store as st
from test_components import record

class S2Classification(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'p';e.init(self.root)
    def tearDown(self):self.tmp.cleanup()
    def classified(self,kind='runtime',**kw):
        return record('s2',s2_type=kind,s2_applicability='current-user' if kind=='interaction' else 'task-environment',s2_context='Synthetic applicable context',state='confirmed',confirmed_by='synthetic',**kw)
    def test_all_types_query_recall_and_legacy(self):
        for kind in e.S2_TYPES:e.add(self.root,self.classified(kind))
        legacy=record('s2');e.add(self.root,legacy)
        for kind in e.S2_TYPES:
            q=e.query(self.root,s2_type=kind)
            self.assertEqual(len(q['records']),1);self.assertEqual(q['effective_preferences'],[])
            item=rv.recall(self.root,s2_type=kind)['items'][0]
            self.assertEqual(item['s2_type'],kind);self.assertEqual(item['s2_context'],'Synthetic applicable context')
        self.assertEqual(e.query(self.root,s2_type='unclassified')['records'][0]['id'],legacy['id'])
    def test_invalid_classification_rejected(self):
        for change in ({'s2_type':'unknown'},{'s2_context':''},{'s2_type':'interaction','s2_applicability':'reusable-method'},{'component':'s1'}):
            row=self.classified();row.update(change)
            with self.assertRaises(ValueError):e.add(self.root,row)
        row=self.classified();row.pop('s2_context')
        with self.assertRaises(ValueError):e.add(self.root,row)
        with self.assertRaises(ValueError):e.query(self.root,component='s1',s2_type='runtime')
    def test_preview_readonly_and_no_inference(self):
        row=record('s2');e.add(self.root,row);before=pb.inventory(self.root)[0]
        preview=e.s2_classification_preview(self.root)
        self.assertEqual(preview['total'],1);self.assertIsNone(preview['items'][0]['suggested_type'])
        self.assertEqual(before,pb.inventory(self.root)[0]);self.assertEqual(e.s1_metrics(self.root)['observations'],0)
    def test_pack_roundtrip_and_feature_marker(self):
        row=self.classified();e.add(self.root,row);pack=self.base/'pack'
        e.export_pack(self.root,pack,['s2'])
        man=e.read(pack/'pack.json');self.assertEqual(man['core_api'],2)
        e.validate_pack(pack)
        target=self.base/'target';e.init(target,e.info(self.root)['profile_id'])
        plan=e.import_plan(target,pack)
        e.import_pack(target,pack,plan['plan_id'])
        self.assertEqual(e.query(target,s2_type='runtime')['records'][0]['id'],row['id'])
        man['core_api']=1;man['pack_id']=st.digest(e.encoded({k:v for k,v in man.items() if k!='pack_id'}));(pack/'pack.json').write_bytes(e.encoded(man))
        with self.assertRaises(ValueError):e.validate_pack(pack)
    def test_legacy_pack_stays_api_one(self):
        e.add(self.root,record('s2'));pack=self.base/'pack';e.export_pack(self.root,pack,['s2'])
        self.assertEqual(e.read(pack/'pack.json')['core_api'],1);e.validate_pack(pack)
    def test_classified_candidate_revision_supersedes_unclassified_original(self):
        legacy=record('s2');e.add(self.root,legacy)
        revision=record('s2',s2_type='runtime',s2_applicability='task-environment',
                        s2_context='Synthetic applicable context',supersedes=legacy['id'])
        e.add(self.root,revision)
        states={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
        self.assertEqual(states[legacy['id']],'superseded')
        self.assertEqual(states[revision['id']],'candidate')
        self.assertEqual(e.s2_classification_preview(self.root)['total'],0)
        self.assertEqual([r['id'] for r in e.query(self.root,s2_type='runtime')['records']],[revision['id']])
    def test_plain_candidate_supersede_keeps_old_active(self):
        a=record('s2');b=record('s2',supersedes=a['id']);e.add(self.root,a);e.add(self.root,b)
        states={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
        self.assertEqual(states[a['id']],'candidate')
        self.assertEqual(states[b['id']],'candidate')
    def test_classification_candidate_cannot_hide_confirmed(self):
        old=record('s2',state='confirmed',confirmed_by='synthetic');e.add(self.root,old)
        new=record('s2',supersedes=old['id'],s2_type='runtime',
                   s2_applicability='task-environment',s2_context='test')
        e.add(self.root,new)
        states={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
        self.assertEqual(states[old['id']],'confirmed')
        self.assertIn(old['id'],[r['id'] for r in rv.recall(self.root)['items']])

    def test_changed_content_classification_keeps_candidate_original(self):
        for field in ('text','evidence','cause','prevention','counter_signal','environment'):
            with self.subTest(field=field):
                old=record('s2');e.add(self.root,old)
                new=record('s2',supersedes=old['id'],s2_type='runtime',
                           s2_applicability='task-environment',s2_context='test')
                new[field]=['changed'] if field=='evidence' else {'os':'other'} if field=='environment' else 'changed'
                e.add(self.root,new)
                states={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
                self.assertEqual(states[old['id']],'candidate')

    def test_cross_scope_multilevel_classification_roundtrip(self):
        old=record('s2');e.add(self.root,old)
        middle={**old,'id':'a'*32,'scope':'personal','supersedes':old['id'],
                's2_type':'runtime','s2_applicability':'task-environment','s2_context':'test'}
        new={**middle,'id':'b'*32,'supersedes':middle['id'],'s2_type':'execution'}
        e.add(self.root,middle);e.add(self.root,new)
        plan=e.export_plan(self.root,['s2'],scope='work')
        self.assertTrue(plan['needs_confirmation']);self.assertEqual(len(plan['files']),3)
        pack=self.base/'scope-pack';e.export_pack(self.root,pack,['s2'],scope='work',plan_id=plan['plan_id'])
        target=self.base/'scope-target';e.init(target,e.info(self.root)['profile_id'])
        plan=e.import_plan(target,pack);e.import_pack(target,pack,plan['plan_id'])
        self.assertEqual(e.query(self.root)['records'],e.query(target)['records'])

    def test_partial_export_keeps_classification_state(self):
        old=record('s2',module='old');e.add(self.root,old)
        new={**old,'id':'f'*32,'module':'new','supersedes':old['id'],
             's2_type':'runtime','s2_applicability':'task-environment','s2_context':'test'}
        e.add(self.root,new)
        pack=self.base/'partial';preview=e.export_plan(self.root,['s2'],module='old')
        self.assertTrue(preview['needs_confirmation'])
        with self.assertRaises(ValueError):e.export_pack(self.root,pack,['s2'],module='old')
        e.export_pack(self.root,pack,['s2'],module='old',plan_id=preview['plan_id'])
        target=self.base/'target';e.init(target,e.info(self.root)['profile_id'])
        plan=e.import_plan(target,pack);e.import_pack(target,pack,plan['plan_id'])
        states=lambda root:{r['id']:r['effective_state'] for r in e.query(root)['records']}
        self.assertEqual(states(self.root),states(target))
    def test_classified_backup_restore(self):
        row=self.classified('interaction');e.add(self.root,row)
        backup=self.base/'backup';plan=pb.backup_plan(self.root);pb.backup(self.root,backup,plan['plan_id'])
        target=self.base/'restored';plan=pb.restore_plan(backup,target);pb.restore(backup,target,plan['plan_id'])
        self.assertEqual(e.query(self.root,s2_type='interaction'),e.query(target,s2_type='interaction'))
    def test_cli_filter(self):
        e.add(self.root,self.classified('reasoning'))
        p=subprocess.run([sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'--profile',str(self.root),'recall','--s2-type','reasoning'],capture_output=True,encoding='utf-8')
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['items'][0]['s2_type'],'reasoning')
