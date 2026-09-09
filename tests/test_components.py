from pathlib import Path
import io,os,sys,json,tempfile,unittest,uuid,subprocess,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e
import safe_store as st
import core_package as cp
import release_gate as gate

def test_review(root,path):
    receipt=gate.draft(root)
    # This fixture only acknowledges the literal synthetic Windows path in this test source.
    for f in receipt['findings_to_review']:
        if f['file']!='tests/test_components.py' or f['rule']!='absolute-windows-path':
            raise AssertionError('Unexpected real-source privacy finding: '+str(f))
    receipt.update(state='reviewed',review_reference='Synthetic automated-test receipt; not publication approval',
                   attestations={k:True for k in gate.ATTESTATIONS},
                   accepted_findings={f['id']:'Literal synthetic path used to test traversal rejection.' for f in receipt['findings_to_review']})
    path.write_bytes(e.encoded(receipt));return path

def record(component='s1',**kw):
    value=dict(id=uuid.uuid4().hex,component=component,module='documents',scope='work',category='writing',
               state='candidate',text='Synthetic observation',task_id='synthetic-task',created_at='2026-01-01T00:00:00Z',evidence=['Synthetic evidence'])
    if component=='s2':value.update(cause='Synthetic cause',prevention='Check output',counter_signal='Wrong output',environment={})
    value.update(kw);return value

def event(source='synthetic:one',**kw):
    row=dict(policy='plan-a-v1',preference_id='brief',scope='work',module='documents',text='Brief',source=source,
             evidence='Synthetic evidence',device='synthetic-device',date='2026-01-01',kind='explicit',confirmed_by='synthetic yes')
    row.update(kw);return row

def outcome(task_id='task-1',lesson_id='0'*32,**kw):
    row=dict(schema=1,task_id=task_id,lesson_id=lesson_id,opportunity=True,
             recalled=False,applied=False,recurred=False,evidence='Synthetic observation',
             created_at='2026-09-06T00:00:00Z')
    row.update(kw);return row

def s1outcome(task_id='task-1',**kw):
    row=dict(schema=2,task_id=task_id,scope='work',fewer_followups=True,
             opportunity=True,recalled=True,applied=True,hit=True,
             preference_id='brief',module='documents',evidence='Synthetic S1 observation',
             created_at='2026-09-06T00:00:00Z')
    row.update(kw);return row

class Components(unittest.TestCase):

    def test_query_capture_avoids_record_reparse_read(self):
        row=record(state='confirmed',confirmed_by='synthetic confirmation');e.add(self.root,row)
        original=e.read
        def guarded(path):
            if Path(path).parent.name in ('records','events'):
                raise AssertionError('Redundant record read')
            return original(path)
        with patch.object(e,'read',side_effect=guarded):
            self.assertEqual(e.query(self.root)['records'][0]['id'],row['id'])

    def test_query_capture_detects_same_size_mutation(self):
        row=record(text='Before',state='confirmed',confirmed_by='synthetic confirmation');e.add(self.root,row)
        target=self.root/'s1/records'/(row['id']+'.json')
        prior=target.stat();original=e.decode_row;changed=[]
        def mutate(data):
            result=original(data)
            if isinstance(result,dict) and result.get('id')==row['id'] and not changed:
                changed.append(True)
                target.write_bytes(target.read_bytes().replace(b'Before',b'After!'))
                os.utime(target,ns=(prior.st_atime_ns,prior.st_mtime_ns))
            return result
        with patch.object(e,'decode_row',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed during read'):e.query(self.root)
        self.assertEqual(e.query(self.root)['records'][0]['text'],'After!')

    def test_query_capture_no_cross_profile_or_stale_revision_cache(self):
        other=self.base/'isolated';e.init(other)
        row=record(text='Old',state='confirmed',confirmed_by='synthetic confirmation');e.add(self.root,row)
        self.assertEqual(len(e.query(self.root)['records']),1)
        self.assertEqual(e.query(other)['records'],[])
        new=record(text='Corrected',state='confirmed',confirmed_by='synthetic confirmation',supersedes=row['id']);e.add(self.root,new)
        states={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
        self.assertEqual(states[row['id']],'superseded')
        self.assertEqual(states[new['id']],'confirmed')

    def test_intro_verified_version_and_current_capabilities(self):
        value=e.introduction()
        self.assertEqual(value['version'],cp.verify(e.CORE)['version'])
        self.assertEqual({c['id'] for c in value['capabilities']},{'recall','personal-experience','error-review','skill-review','migration','outcomes','updates','backup','diagnostics'})
        self.assertIn(value['profile_state'],('bound-valid','needs-setup-or-repair','not-inspected'))
        for card in value['capabilities']:
            self.assertTrue(card['ability'] and card['example'] and card['advice'])

    def test_intro_adapts_to_user_focus(self):
        for focus,first in [('general','recall'),('work','error-review'),('personal','personal-experience'),('migration','migration'),('updates','updates')]:
            self.assertEqual(e.introduction(focus=focus)['capabilities'][0]['id'],first)
        with self.assertRaises(ValueError):e.introduction(focus='unsupported')

    def test_intro_needs_no_binding_network_or_profile_content(self):
        with patch.object(e,'profile_root',side_effect=AssertionError('Unrequested private access')), \
             patch.object(e,'query',side_effect=AssertionError('Private record access')), \
             patch('urllib.request.urlopen',side_effect=AssertionError('Network')):
            self.assertEqual(e.introduction()['source'],'verified-local-core')

    def test_intro_explicit_profile_readonly_and_no_private_leak(self):
        e.add(self.root,record(text='PRIVATE_SENTINEL_DO_NOT_REVEAL'))
        before={p.relative_to(self.root).as_posix():st.hash_file(p) for p in self.root.rglob('*') if p.is_file()}
        value=e.introduction(profile=self.root)
        self.assertEqual(value['profile_state'],'metadata-valid-records-not-audited')
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(value))
        self.assertEqual(before,{p.relative_to(self.root).as_posix():st.hash_file(p) for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(e.introduction(profile=self.base/'missing')['profile_state'],'needs-setup-or-repair')

    def test_intro_default_probe_reads_binding_metadata_only(self):
        probe=self.base/'probe'/'installation.json'
        with patch.object(e,'binding_path',return_value=probe):
            self.assertEqual(e.introduction()['profile_state'],'needs-setup-or-repair')
            self.assertFalse(probe.exists())
        e.add(self.root,record(text='PROBE_SENTINEL_DO_NOT_REVEAL'))
        bound=self.base/'bound'/'installation.json'
        bound.parent.mkdir(parents=True)
        bound.write_bytes(e.encoded({'schema':e.FORMAT,'core_series':'modular-1','profile_root':str(self.root)}))
        with patch.object(e,'binding_path',return_value=bound):
            value=e.introduction()
        self.assertEqual(value['profile_state'],'bound-valid')
        self.assertNotIn('PROBE_SENTINEL_DO_NOT_REVEAL',json.dumps(value))
        bad=self.base/'bad'/'installation.json'
        bad.parent.mkdir(parents=True)
        bad.write_bytes(e.encoded({'schema':e.FORMAT,'profile_root':str(self.base/'missing')}))
        with patch.object(e,'binding_path',return_value=bad):
            self.assertEqual(e.introduction()['profile_state'],'needs-setup-or-repair')

    def test_windows_launcher_scripts_ascii_and_in_manifest(self):
        meta=e.read(e.CORE/'CORE.json')
        for rel in ('scripts/re-cli.ps1','scripts/verify-core.ps1'):
            self.assertIn(rel,meta['files'])
            raw=(e.CORE/rel).read_bytes()
            self.assertFalse(any(b>=128 for b in raw),rel+' must stay ASCII for PowerShell 5.1')
        cli=(e.CORE/'scripts/re-cli.ps1').read_text(encoding='utf-8')
        self.assertIn('Test-PythonVersionText',cli)

    def test_compat_and_feedback_docs_bound_to_manifest_and_gate(self):
        meta=e.read(e.CORE/'CORE.json')
        for rel in ('references/compatibility-matrix.md','references/feedback-template.md'):
            self.assertIn(rel,meta['files'])
            self.assertTrue(gate.permitted(rel))
        matrix=(e.CORE/'references/compatibility-matrix.md').read_text(encoding='utf-8')
        self.assertIn('最低起点 v0.15.0-beta.1',matrix)
        self.assertIn('core_api=2',matrix)
        template=(e.CORE/'references/feedback-template.md').read_text(encoding='utf-8')
        self.assertIn('unknown',template)

    def test_intro_tracks_changed_core_and_missing_capability(self):
        import shutil
        clone=self.base/'core';shutil.copytree(e.CORE,clone,ignore=shutil.ignore_patterns('__pycache__'))
        path=clone/'scripts/experience.py';data=path.read_text(encoding='utf-8')
        path.write_text(data.replace("sub.add_parser('observe-s1')","sub.add_parser('observe-s1-disabled')"),encoding='utf-8')
        meta=e.read(clone/'CORE.json');meta['version']='0.99.0';meta['files']['scripts/experience.py']=st.hash_file(path)
        (clone/'CORE.json').write_bytes(e.encoded(meta))
        value=e.introduction(core=clone)
        self.assertEqual(value['version'],'0.99.0')
        self.assertNotIn('outcomes',{c['id'] for c in value['capabilities']})
        path.write_text(data,encoding='utf-8')
        with self.assertRaises(ValueError):e.introduction(core=clone)

    def test_intro_cli_works_on_unbound_fresh_environment(self):
        env=os.environ.copy();env.update(LOCALAPPDATA=str(self.base/'unbound'),XDG_DATA_HOME=str(self.base/'unbound'))
        result=subprocess.run([sys.executable,'-B',str(e.CORE/'scripts/experience.py'),'intro','--focus','migration'],env=env,capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['capabilities'][0]['id'],'migration')
        self.assertFalse((self.base/'unbound').exists())

    def test_intro_missing_release_script_omits_updates(self):
        import shutil
        clone=self.base/'core';shutil.copytree(e.CORE,clone,ignore=shutil.ignore_patterns('__pycache__'))
        meta=e.read(clone/'CORE.json');meta['files'].pop('scripts/release_update.py')
        (clone/'scripts/release_update.py').unlink()  # This test's temporary clone only.
        (clone/'CORE.json').write_bytes(e.encoded(meta))
        self.assertNotIn('updates',{c['id'] for c in e.introduction(core=clone)['capabilities']})

    def test_intro_pending_transaction_and_broken_policy_not_ready(self):
        with patch.object(st,'pending',return_value=['synthetic']):
            self.assertEqual(e.introduction(profile=self.root)['profile_state'],'needs-setup-or-repair')
        (self.root/'preferences/policy.json').write_text('{}',encoding='utf-8')
        self.assertEqual(e.introduction(profile=self.root)['profile_state'],'needs-setup-or-repair')

    def test_intro_never_writes_and_refuses_core_changed_during_read(self):
        with patch.object(st,'atomic_bytes',side_effect=AssertionError('Write')), \
             patch.object(st,'apply',side_effect=AssertionError('Transaction')):
            e.introduction(profile=self.root)
        verified=cp.verify(e.CORE)
        with patch.object(cp,'verify',side_effect=[verified,{**verified,'sha256':'changed'}]):
            with self.assertRaisesRegex(ValueError,'Core changed'):e.introduction()

    def test_path_safety_uses_one_metadata_read_per_component(self):
        target=self.root/'profile.json'
        original=Path.lstat
        with patch.object(Path,'lstat',autospec=True,side_effect=original) as calls, \
             patch.object(Path,'exists',side_effect=AssertionError('Redundant stat')), \
             patch.object(Path,'is_file',side_effect=AssertionError('Redundant stat')), \
             patch.object(Path,'is_symlink',side_effect=AssertionError('Redundant stat')):
            self.assertEqual(st.no_links(target),target.absolute())
            self.assertEqual(calls.call_count,len(target.absolute().parents)+1)

    def test_path_safety_rejects_link_metadata_and_preserves_missing_paths(self):
        import stat
        from types import SimpleNamespace
        target=self.root/'profile.json';original=Path.lstat
        for mode,attributes,links in ((stat.S_IFLNK,0,1),(stat.S_IFDIR,0x400,1),(stat.S_IFREG,0,2)):
            def metadata(path):
                return SimpleNamespace(st_mode=mode,st_file_attributes=attributes,st_nlink=links) if path==target else original(path)
            with patch.object(Path,'lstat',autospec=True,side_effect=metadata):
                with self.assertRaises(ValueError):st.no_links(target)
        missing=self.root/'absent'/'new.json'
        self.assertEqual(st.no_links(missing),missing.absolute())
        with patch.object(Path,'lstat',side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):st.no_links(target)

    def test_read_guard_detects_same_size_edit_with_restored_timestamp(self):
        row=record(text='Alpha');e.add(self.root,row)
        target=self.root/'s1/records'/(row['id']+'.json');before=target.stat()
        with self.assertRaisesRegex(ValueError,'changed during read'):
            with e.read_guard(self.root):
                target.write_bytes(target.read_bytes().replace(b'Alpha',b'Bravo'))
                os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'source';self.meta=e.init(self.root)
    def tearDown(self):self.tmp.cleanup()
    def target(self):
        root=self.base/uuid.uuid4().hex;e.init(root,self.meta['profile_id']);return root
    def pack(self,components=('s1','s2')):
        out=self.base/uuid.uuid4().hex;e.export_pack(self.root,out,components);return out
    def test_roundtrip_separate_components_idempotent_scores(self):
        e.add(self.root,record());e.add(self.root,record('s2'));e.add_event(self.root,event())
        pack=self.pack(('s1',));man,rows=e.validate_pack(pack)
        self.assertFalse(any(r.startswith('s2/') for r in rows))
        target=self.target();plan=e.import_plan(target,pack)
        self.assertEqual(e.import_pack(target,pack,plan['plan_id'])['added'],2)
        before=e.profile_digest(target);plan=e.import_plan(target,pack)
        self.assertEqual(e.import_pack(target,pack,plan['plan_id'])['status'],'unchanged')
        self.assertEqual(before,e.profile_digest(target))
        self.assertEqual(e.query(self.root)['effective_preferences'],e.query(target)['effective_preferences'])
    def test_s2_pack_does_not_include_s1_or_code_or_legacy(self):
        e.add(self.root,record('s2'));e.add_event(self.root,event())
        st.atomic_bytes(self.root/'legacy/private.md',b'PRIVATE');st.atomic_bytes(self.root/'s3-private/private.json',b'{}')
        man,rows=e.validate_pack(self.pack(('s2',)))
        self.assertEqual(len(rows),1);self.assertTrue(all(rel.startswith('s2/') for rel in rows))
    def test_partial_export_keeps_state_and_requires_preview(self):
        a=record(scope='personal');e.add(self.root,a)
        b=record(scope='work',supersedes=a['id'],state='confirmed',confirmed_by='synthetic yes')
        e.add(self.root,b)
        for scope,added_id,reason in (('work',a['id'],'reference'),
                                      ('personal',b['id'],'keeps-superseded-state')):
            with self.subTest(scope=scope):
                plan=e.export_plan(self.root,['s1'],scope=scope)
                self.assertTrue(plan['needs_confirmation'])
                self.assertEqual(plan['expansion_count'],1)
                self.assertTrue(any(x['id']==added_id and reason in x['reasons']
                                    for x in plan['additions']))
                out=self.base/('filtered-'+scope)
                with self.assertRaises(ValueError):
                    e.export_pack(self.root,out,['s1'],scope=scope)
                e.export_pack(self.root,out,['s1'],scope=scope,plan_id=plan['plan_id'])
                self.assertEqual(len(e.validate_pack(out)[1]),2)
                target=self.target()
                p2=e.import_plan(target,out);e.import_pack(target,out,p2['plan_id'])
                src={r['id']:r['effective_state'] for r in e.query(self.root)['records']}
                dst={r['id']:r['effective_state'] for r in e.query(target)['records']}
                for rid in (a['id'],b['id']):
                    self.assertEqual(src[rid],dst[rid])
                self.assertEqual(dst[a['id']],'superseded')
                self.assertEqual(dst[b['id']],'confirmed')
    def test_cross_component_supersede_rejected(self):
        a=record('s2');e.add(self.root,a)
        before=e.profile_digest(self.root)
        with self.assertRaises(ValueError):e.add(self.root,record(supersedes=a['id']))
        self.assertEqual(before,e.profile_digest(self.root))
    def test_retire_marker_and_confirmed_restore_protocol(self):
        a=record(state='confirmed',confirmed_by='synthetic yes');e.add(self.root,a)
        marker=record(state='retired',supersedes=a['id']);e.add(self.root,marker)
        states={r['id']:r for r in e.query(self.root)['records']}
        self.assertEqual(states[a['id']]['effective_state'],'retired')
        self.assertEqual(states[marker['id']]['marker'],'retire')
        replacement=record(state='confirmed',supersedes=a['id'],confirmed_by='synthetic yes')
        e.add(self.root,replacement)
        states={r['id']:r for r in e.query(self.root)['records']}
        self.assertEqual(states[a['id']]['effective_state'],'superseded')
    def test_task_query_returns_matching_raw_events(self):
        e.add_event(self.root,event(source='synthetic:task-one',task_id='one'))
        e.add_event(self.root,event(source='synthetic:task-two',task_id='two'))
        e.add(self.root,record(task_id='one'))
        q=e.query(self.root,task_id='one')
        self.assertEqual([x['task_id'] for x in q['events']],['one'])
        self.assertEqual(q['effective_preferences'],[])
        self.assertEqual(len(e.query(self.root,text='Brief')['events']),2)
    def test_import_plan_previews_rule_record_changes(self):
        a=record(state='confirmed',confirmed_by='synthetic yes');e.add(self.root,a)
        b=record(state='confirmed',supersedes=a['id'],confirmed_by='synthetic yes',text='Replacement rule')
        e.add(self.root,b)
        pack=self.pack(('s1',))
        target=self.target();e.add(target,a)
        plan=e.import_plan(target,pack)
        self.assertTrue(any(c['id']==a['id'] and c['before']=='confirmed' and c['after']=='superseded'
                            for c in plan['rule_changes']['records']))
        self.assertEqual(e.import_pack(target,pack,plan['plan_id'])['status'],'imported')
        src=self.base/'src2';e.init(src,self.meta['profile_id'])
        first=event(source='synthetic:first');e.add_event(src,first)
        second=event(source='synthetic:second',text='Different brief');e.add_event(src,second)
        out=self.base/'pack2';e.export_pack(src,out,['s1'])
        target2=self.target();e.add_event(target2,first)
        plan2=e.import_plan(target2,out)
        changed=[c for c in plan2['rule_changes']['preferences']
                 if c['preference_id']=='brief' and 'pending' in c.get('fields',[])]
        self.assertTrue(changed)
        self.assertEqual(e.import_pack(target2,out,plan2['plan_id'])['status'],'imported')
        reasons=[]
        for item in e.query(target2)['pending_preferences']:
            reasons += [p['reason'] for p in item.get('pending',[])]
        self.assertIn('DEFINITION_CONFLICT',reasons)
    def test_different_person_refused(self):
        pack=self.pack();target=self.base/'another';e.init(target)
        with self.assertRaises(ValueError):e.import_plan(target,pack)
    def test_merge_into_current_requires_trust_then_imports(self):
        e.add(self.root,record())
        e.add(self.root,record('s2'))
        pack=self.pack()
        source_id=e.read(pack/'pack.json')['profile_id']
        target=self.base/'merge-current';e.init(target)
        with self.assertRaises(ValueError):
            e.import_plan(target,pack)
        plan=e.import_plan(target,pack,merge_into_current=True)
        self.assertTrue(plan['merge']['merge_into_current'])
        self.assertFalse(plan['merge']['source_trusted'])
        with self.assertRaises(ValueError):
            e.import_pack(target,pack,plan['plan_id'],merge_into_current=True)
        result=e.import_pack(target,pack,plan['plan_id'],merge_into_current=True,
                             trust_reason='synthetic same-owner confirmation')
        self.assertEqual(result['status'],'imported')
        sources=e.trusted_sources_view(target)['sources']
        self.assertEqual([s['source_profile_id'] for s in sources],[source_id])
        plan2=e.import_plan(target,pack,merge_into_current=True)
        self.assertTrue(plan2['merge']['source_trusted'])
        before=e.query(target)['revision']
        self.assertEqual(e.import_pack(target,pack,plan2['plan_id'],
                                       merge_into_current=True)['status'],'unchanged')
        self.assertEqual(e.query(target)['revision'],before)
        self.assertEqual(e.remove_trusted_source(target,source_id)['status'],'removed')
        self.assertFalse(e.is_trusted_source(target,source_id))
    def test_changed_target_plan_refused(self):
        e.add(self.root,record());pack=self.pack();target=self.target();plan=e.import_plan(target,pack)
        e.add(target,record())
        with self.assertRaises(ValueError):e.import_pack(target,pack,plan['plan_id'])
    def test_changed_pack_refused(self):
        e.add(self.root,record());pack=self.pack();man,rows=e.validate_pack(pack)
        rel=next(iter(rows));(pack/rel).write_text('{}')
        with self.assertRaises(ValueError):e.validate_pack(pack)
    def test_unknown_and_executable_payload_refused(self):
        pack=self.pack();(pack/'evil.py').write_text('raise SystemExit')
        with self.assertRaises(ValueError):e.validate_pack(pack)
    def test_unknown_schema_and_duplicate_json_refused(self):
        pack=self.pack();man=e.read(pack/'pack.json');man['format']=999
        st.atomic_bytes(pack/'pack.json',e.encoded(man))
        with self.assertRaises(ValueError):e.validate_pack(pack)
        (pack/'pack.json').write_text('{"format":1,"format":1}')
        with self.assertRaises(ValueError):e.validate_pack(pack)
    def test_path_traversal_reserved_ads(self):
        windows_abs = 'C' + ':/a'
        for path in ('../a','/a',windows_abs,'x:stream','CON','a/../b','a\\b'):
            with self.subTest(path=path),self.assertRaises(ValueError):st.relative(path)
    def test_immutable_conflict(self):
        r=record();e.add(self.root,r)
        with self.assertRaises(ValueError):e.add(self.root,{**r,'text':'changed'})
    def test_pending_supersedes_does_not_disable_original(self):
        a=record(state='confirmed',confirmed_by='synthetic yes');e.add(self.root,a)
        e.add(self.root,record(supersedes=a['id']))
        self.assertEqual(next(r for r in e.query(self.root)['records'] if r['id']==a['id'])['effective_state'],'confirmed')
    def test_dependency_missing_blocks_event(self):
        with self.assertRaises(ValueError):e.add_event(self.root,event(kind='decision',target='a'*64,basis=['a'*64],choice='keep'))
    def test_query_changes_no_experience_or_revision(self):
        e.add(self.root,record());before=e.profile_digest(self.root)
        e.query(self.root);self.assertEqual(before,e.profile_digest(self.root))
    def test_read_paths_never_open_writer_lock(self):
        e.add(self.root,record())
        with patch.object(st,'locked',side_effect=AssertionError('read attempted write lock')):
            e.query(self.root);e.query_s3(self.root)
            self.pack()
    def test_read_snapshot_refuses_concurrent_write(self):
        with self.assertRaises(ValueError):
            with e.read_guard(self.root):
                e.add(self.root,record())
    def test_task_query_omits_unrelated_preferences(self):
        e.add_event(self.root,event());e.add(self.root,record(task_id='one'));e.add(self.root,record(task_id='two'))
        q=e.query(self.root,task_id='one');self.assertEqual(len(q['records']),1);self.assertEqual(q['effective_preferences'],[])
    def test_s2_query_excludes_pending_s1_scores(self):
        e.add_event(self.root,event(kind='support',classification_state='staged'))
        self.assertTrue(e.query(self.root,component='s1')['pending_preferences'])
        with patch.object(e.pe,'snapshot',side_effect=AssertionError('S2 invoked scoring')):
            q=e.query(self.root,component='s2')
        self.assertEqual(q['pending_preferences'],[])
        self.assertEqual(q['effective_preferences'],[])
    def test_non_s1_scoring_events_refused_on_add_and_import(self):
        for component in ('s2','s3'):
            row=event(component=component)
            before=e.profile_digest(self.root)
            with self.assertRaises(ValueError):e.add_event(self.root,row)
            self.assertEqual(before,e.profile_digest(self.root))
            pack=self.pack(('s1',));man=e.read(pack/'pack.json')
            rel='preferences/events/'+e.pe.event_id(row)+'.json';data=e.encoded(row)
            st.atomic_bytes(pack/rel,data)
            man['files'][rel]={'sha256':st.digest(data),'bytes':len(data)}
            man.pop('pack_id');man['pack_id']=st.digest(e.encoded(man))
            st.atomic_bytes(pack/'pack.json',e.encoded(man))
            with self.assertRaises(ValueError):e.import_plan(self.target(),pack)
    def test_s1_legacy_scores_unchanged_by_s2_and_s3(self):
        for scope in ('work','personal','general'):
            e.add_event(self.root,event(source='synthetic:'+scope,scope=scope))
        before=e.query(self.root,component='s1')['effective_preferences']
        self.assertEqual(len(before),3)
        e.add(self.root,record('s2'))
        e.log_s3(self.root,dict(task_id='test',text='Synthetic iteration',evidence='Synthetic'))
        self.assertEqual(e.query(self.root,component='s1')['effective_preferences'],before)
        e.pe.validate(event(component='s1'))
    def test_transaction_failure_restores_existing_data(self):
        before=e.profile_digest(self.root);original=st.atomic_bytes
        def fail(path,data,*a,**kw):
            if Path(path)==self.root/'profile.json':raise OSError('synthetic disk failure')
            return original(path,data,*a,**kw)
        with patch.object(st,'atomic_bytes',fail),self.assertRaises(OSError):e.add(self.root,record())
        self.assertEqual(before,e.profile_digest(self.root))
    def test_s3_not_in_export(self):
        e.log_s3(self.root,dict(task_id='test',text='PRIVATE ITERATION',evidence='synthetic'))
        self.assertEqual(e.validate_pack(self.pack())[1],{})
        self.assertEqual(len(e.query_s3(self.root,task_id='test')['records']),1)
        self.assertEqual(e.query_s3(self.root,task_id='other')['records'],[])
    def test_s3_query_refuses_external_changes_without_revision(self):
        e.log_s3(self.root,dict(task_id='test',text='Synthetic',evidence='Synthetic'))
        path=next((self.root/'s3-private').glob('*.json'))
        original=e.read;before=e.info(self.root)['revision']
        for operation in ('modify','remove','add'):
            data=path.read_bytes()
            other=path.with_name('a'*64+'.json')
            def changing_read(p):
                row=original(p)
                if Path(p)==path:
                    if operation=='modify':path.write_bytes(data+b' ')
                    elif operation=='remove':path.unlink()
                    else:other.write_bytes(data)
                return row
            with self.subTest(operation=operation),patch.object(e,'read',changing_read):
                with self.assertRaises(ValueError):e.query_s3(self.root)
            path.write_bytes(data)
            if other.exists():other.unlink()
            self.assertEqual(e.info(self.root)['revision'],before)
        self.assertEqual(len(e.query_s3(self.root)['records']),1)
    def test_core_independent_from_profile_and_clean_export(self):
        marker=uuid.uuid4().hex+uuid.uuid4().hex
        before=cp.verify(e.CORE);e.add(self.root,record(text=marker))
        self.assertEqual(before,cp.verify(e.CORE))
        out=self.base/'core';cp.export(e.CORE,out,test_review(e.CORE,self.base/'review.json'))
        self.assertEqual((out/'CORE.json').read_bytes(),(e.CORE/'CORE.json').read_bytes())
        self.assertFalse(any(marker.encode() in p.read_bytes() for p in out.rglob('*') if p.is_file()))
    def test_core_missing_or_unknown_file_rejected(self):
        out=self.base/'core';cp.export(e.CORE,out,test_review(e.CORE,self.base/'review.json'));(out/'leak.json').write_text('{}')
        with self.assertRaises(ValueError):cp.verify(out)
    def test_package_size_budget(self):
        e.add(self.root,record());pack=self.pack()
        with patch.object(e,'MAX_FILE',10),self.assertRaises(ValueError):e.validate_pack(pack)
    def test_import_combined_capacity_refused_without_mutation(self):
        e.add(self.root,record());pack=self.pack();target=self.target()
        e.add(target,record());plan=e.import_plan(target,pack)
        before=e.profile_digest(target)
        size=sum(p.stat().st_size for p in e.payloads(target).values())
        for limit in ({'MAX_FILES':1},{'MAX_TOTAL':size+1}):
            with self.subTest(limit=limit),patch.multiple(e,**limit):
                with self.assertRaises(ValueError):e.import_plan(target,pack)
                with self.assertRaises(ValueError):e.import_pack(target,pack,plan['plan_id'])
                self.assertEqual(e.profile_digest(target),before)
                self.assertEqual(len(e.query(target)['records']),1)
                self.assertEqual(st.pending(target),[])
    def test_add_and_event_capacity_boundaries(self):
        for kind in ('record','event'):
            root=self.target();e.add(root,record())
            row=record(text='Synthetic '*100) if kind=='record' else event(text='Synthetic '*100)
            write=e.add if kind=='record' else e.add_event
            size=sum(p.stat().st_size for p in e.payloads(root).values());n=len(e.encoded(row))
            before=e.profile_digest(root)
            for limit in ({'MAX_FILES':1},{'MAX_TOTAL':size+n-1},{'MAX_FILE':n-1}):
                with self.subTest(kind=kind,limit=limit),patch.multiple(e,**limit):
                    with self.assertRaises(ValueError):write(root,row)
                    self.assertEqual(e.profile_digest(root),before)
                    e.query(root)
            with patch.multiple(e,MAX_FILES=2,MAX_TOTAL=size+n,MAX_FILE=n):
                self.assertEqual(write(root,row)['status'],'added')
                at_limit=e.profile_digest(root)
                self.assertEqual(write(root,row)['status'],'unchanged')
                self.assertEqual(e.profile_digest(root),at_limit)
                e.query(root)
    def test_import_capacity_uses_preserved_bytes_and_serialized_incoming(self):
        e.add(self.root,record());pack=self.pack();target=self.target()
        a=record();e.add(target,a)
        path=next(iter(e.payloads(target).values()))
        # Existing formatting is preserved, incoming JSON is reserialized at commit.
        path.write_bytes(e.encoded(a)+b' '*2000)
        incoming=e.validate_pack(pack)[1]
        n=sum(len(e.encoded(r)) for r in incoming.values())
        exact=path.stat().st_size+n;before=e.profile_digest(target)
        with patch.object(e,'MAX_TOTAL',exact-1):
            with self.assertRaises(ValueError):e.import_plan(target,pack)
            self.assertEqual(e.profile_digest(target),before)
        with patch.object(e,'MAX_TOTAL',exact):
            plan=e.import_plan(target,pack)
            self.assertEqual(e.import_pack(target,pack,plan['plan_id'])['status'],'imported')
            self.assertEqual(len(e.query(target)['records']),2)
            plan=e.import_plan(target,pack)
            self.assertEqual(e.import_pack(target,pack,plan['plan_id'])['status'],'unchanged')
    def test_import_compact_payload_expansion_checked_before_commit(self):
        row=record(text='Synthetic '*1000,evidence=['Synthetic']*1000)
        e.add(self.root,row);pack=self.pack();target=self.target()
        man=e.read(pack/'pack.json');rel=next(iter(man['files']))
        compact=json.dumps(row,separators=(',',':')).encode('utf-8')
        st.atomic_bytes(pack/rel,compact)
        man['files'][rel]={'sha256':st.digest(compact),'bytes':len(compact)}
        man.pop('pack_id');man['pack_id']=st.digest(e.encoded(man))
        st.atomic_bytes(pack/'pack.json',e.encoded(man))
        before=e.profile_digest(target)
        with patch.object(e,'MAX_FILE',len(compact)):
            e.validate_pack(pack)
            with self.assertRaises(ValueError):e.import_plan(target,pack)
            self.assertEqual(e.profile_digest(target),before)
    def test_s2_outcome_requires_lesson_and_flag_constraints(self):
        lesson=record('s2');e.add(self.root,lesson)
        row=outcome(task_id='x',lesson_id=lesson['id'],opportunity=True,recalled=True,applied=True,recurred=False)
        self.assertEqual(e.log_s2_outcome(self.root,row)['status'],'logged')
        self.assertEqual(e.log_s2_outcome(self.root,row)['status'],'unchanged')
        self.assertEqual(len(e.outcome_rows(self.root)),1)
        with self.assertRaises(ValueError):
            e.log_s2_outcome(self.root,outcome(lesson_id='1'*32))
        for bad in (outcome(lesson_id=lesson['id'],opportunity=False,recalled=True),
                    outcome(lesson_id=lesson['id'],opportunity=True,recalled=False,applied=True),
                    outcome(lesson_id=lesson['id'],opportunity=True,recalled=True,applied=True,recurred=True,evidence='')):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                e.log_s2_outcome(self.root,bad)
    def test_s2_metrics_distinct_tasks_and_avoided_candidate(self):
        lesson=record('s2');e.add(self.root,lesson)
        for t in ('t1','t2','t3'):
            e.log_s2_outcome(self.root,outcome(task_id=t,lesson_id=lesson['id'],
                                               recalled=True,applied=True,recurred=(t=='t3')))
        row=e.s2_metrics(self.root,lesson['id'])['lessons'][0]
        self.assertEqual((row['opportunity_tasks'],row['recall_tasks'],row['apply_tasks'],
                          row['recurrence_tasks'],row['avoided_candidate']),(3,3,3,1,False))
        second=record('s2');e.add(self.root,second)
        for t in ('t4','t5'):
            e.log_s2_outcome(self.root,outcome(task_id=t,lesson_id=second['id'],
                                               recalled=True,applied=True))
        row2=next(x for x in e.s2_metrics(self.root)['lessons'] if x['lesson_id']==second['id'])
        self.assertEqual((row2['opportunity_tasks'],row2['recurrence_tasks'],
                          row2['avoided_candidate']),(2,0,True))
    def test_s2_outcome_not_in_export_and_metrics_readonly(self):
        lesson=record('s2');e.add(self.root,lesson)
        e.log_s2_outcome(self.root,outcome(task_id='x',lesson_id=lesson['id']))
        rows=e.validate_pack(self.pack())[1]
        self.assertFalse(any(rel.startswith('s2-outcomes/') for rel in rows))
        self.assertIn('s2/records/'+lesson['id']+'.json',rows)
        before=e.profile_digest(self.root)
        e.s2_metrics(self.root)
        self.assertEqual(before,e.profile_digest(self.root))
    def test_import_disk_full_rolls_back_all_added_files(self):
        e.add(self.root,record());pack=self.pack();target=self.target()
        plan=e.import_plan(target,pack);before=e.profile_digest(target)
        original=st.atomic_bytes
        def fail_profile(path,data,*a,**kw):
            if Path(path)==target/'profile.json':
                raise OSError('synthetic disk full')
            return original(path,data,*a,**kw)
        with patch.object(st,'atomic_bytes',fail_profile),self.assertRaises(OSError):
            e.import_pack(target,pack,plan['plan_id'])
        self.assertEqual(e.profile_digest(target),before)
        self.assertEqual(st.pending(target),[])
        self.assertEqual(len(e.query(target)['records']),0)
    def test_pending_transaction_blocks_and_recover_restores(self):
        original=st.atomic_bytes
        calls={'journal':0,'profile_failed':False}
        def crash_then_finalize(path,data,*a,**kw):
            p=Path(path)
            if p.name=='journal.json':
                calls['journal']+=1
                if calls['journal']==2:
                    raise OSError('synthetic crash finalizing rollback')
            if p==self.root/'profile.json' and not calls['profile_failed']:
                calls['profile_failed']=True
                raise OSError('synthetic disk full')
            return original(p,data,*a,**kw)
        with patch.object(st,'atomic_bytes',crash_then_finalize),self.assertRaises(OSError):
            e.add(self.root,record())
        pending=st.pending(self.root)
        self.assertEqual(len(pending),1)
        with self.assertRaises(ValueError):e.add(self.root,record())
        st.recover(self.root,pending[0])
        self.assertEqual(st.pending(self.root),[])
        r=record();e.add(self.root,r);self.assertEqual(len(e.query(self.root)['records']),1)
    def test_s3_status_fields_and_filter(self):
        e.log_s3(self.root,dict(task_id='a',text='observation',evidence='synthetic'))
        with self.assertRaises(ValueError):
            e.log_s3(self.root,dict(task_id='b',text='distilled',evidence='synthetic',status='distilled'))
        e.log_s3(self.root,dict(task_id='b',text='distilled',evidence='synthetic',status='distilled',
                                review_reference='synthetic review',module='software',category='workflow'))
        e.log_s3(self.root,dict(task_id='c',text='in core',evidence='synthetic',status='in-core',
                                review_reference='core manifest hash'))
        self.assertEqual(len(e.query_s3(self.root,status='observation')['records']),1)
        self.assertEqual(len(e.query_s3(self.root,status='distilled')['records']),1)
        with self.assertRaises(ValueError):
            e.log_s3(self.root,dict(task_id='d',text='x',evidence='y',status='invalid'))
    def test_promotion_suggestions_are_readonly_advisory(self):
        e.add(self.root,record(text='Repeated preference-like rule',task_id='t1'))
        e.add(self.root,record(text='Repeated preference-like rule',task_id='t2'))
        e.add_event(self.root,event(preference_id='concise',text='Always be concise',scope='work'))
        e.add(self.root,record(text='Always be concise',task_id='t3'))
        before=e.profile_digest(self.root)
        q=e.query(self.root,component='s1')
        kinds={s['kind'] for s in q['promotion_suggestions']}
        self.assertIn('repeated-observation',kinds)
        self.assertIn('matches-preference',kinds)
        self.assertTrue(all(s['advisory'] for s in q['promotion_suggestions']))
        self.assertEqual(before,e.profile_digest(self.root))
    def test_update_ledger_mark_status_and_toggle(self):
        self.assertTrue((self.root/'updates').is_dir())
        first=e.updates_status(self.root)
        self.assertEqual(first['min_interval_days'],21)
        self.assertTrue(first['repo']['due'])
        e.mark_updates(self.root,{'channel':'repo','checked_at':'2026-09-06T00:00:00Z',
                                  'summary':'repo exists but no published release',
                                  'repo_status':'repo_ready','new_items':0})
        after=e.updates_status(self.root)
        self.assertEqual(after['repo']['last_checked_at'],'2026-09-06T00:00:00Z')
        self.assertFalse(after['repo']['due'])
        e.mark_updates(self.root,{'channel':'repo','checked_at':'2026-09-06T01:00:00Z',
                                  'summary':'disable reminders','reminders_enabled':False})
        self.assertFalse(e.updates_status(self.root)['reminders_enabled'])
        with self.assertRaises(ValueError):
            e.mark_updates(self.root,{'channel':'other','checked_at':'2026-09-06T00:00:00Z',
                                      'summary':'bad'})
    def test_scene_census_emits_advisory_merge_proposal_without_mutation(self):
        for module,task in (('Software','t1'),('software','t2'),('SOFTWARE','t3'),
                            ('documents','t4'),('document','t5')):
            e.add(self.root,record(module=module,task_id=task))
        before=e.profile_digest(self.root)
        census=e.scene_census(self.root,threshold=2)
        self.assertTrue(census['triggered'])
        self.assertEqual(census['distinct_modules'],5)
        kinds={x['kind'] for x in census['proposal']}
        self.assertIn('label-variant',kinds)
        self.assertIn('similar-label',kinds)
        self.assertEqual(before,e.profile_digest(self.root))
        with self.assertRaises(ValueError):
            e.scene_census(self.root,threshold=1)
    def test_update_ledger_schema2_brief_and_status(self):
        e.mark_updates(self.root,{'channel':'ecosystem','checked_at':'2026-09-06T02:00:00Z',
                                  'summary':'two candidate skills found','new_items':2,
                                  'brief':{'summary':'two candidates','items':[]}})
        ledger=e.load_update_ledger(self.root)
        self.assertEqual(ledger['schema'],2)
        self.assertEqual(ledger['ecosystem']['new_items'],2)
        self.assertEqual(ledger['ecosystem']['last_brief'],{'summary':'two candidates','items':[]})
        e.mark_updates(self.root,{'channel':'repo','checked_at':'2026-09-06T03:00:00Z',
                                  'summary':'no published release','latest_version':'0.9.8'})
        status=e.updates_status(self.root)
        self.assertEqual(status['repo']['latest_version'],'0.9.8')
    def test_updates_check_dry_run_is_local_skeleton_without_network(self):
        brief=e.updates_check_dry_run(self.root)
        self.assertTrue(brief['dry_run'])
        self.assertIsInstance(brief['local_version'],str)
        self.assertEqual(brief['brief']['sections'][0]['items'],[])
        self.assertEqual(brief['item_template']['decision'],'pending-user')
        self.assertTrue(any('No network performed' in n for n in brief['notes']))
    def test_s1_outcome_and_metrics(self):
        e.add_event(self.root,event())
        self.assertEqual(e.log_s1_outcome(self.root,s1outcome(task_id='t1'))['status'],'logged')
        self.assertEqual(e.log_s1_outcome(self.root,s1outcome(task_id='t1'))['status'],'unchanged')
        self.assertEqual(len(e.s1_outcome_rows(self.root)),1)
        with self.assertRaises(ValueError):
            e.log_s1_outcome(self.root,s1outcome(task_id='t2',fewer_followups='yes'))
        with self.assertRaises(ValueError):
            e.log_s1_outcome(self.root,s1outcome(task_id='t3',preference_id='Bad ID'))
        e.log_s1_outcome(self.root,s1outcome(task_id='t2',fewer_followups=False,preference_id=None,hit=False))
        before=e.profile_digest(self.root)
        metrics=e.s1_metrics(self.root,scope='work')['metrics']
        self.assertEqual(sum(x['task_count'] for x in metrics),2)
        self.assertEqual(sum(x['hit_count'] for x in metrics),1)
        self.assertEqual(sum(x['fewer_followups_tasks'] for x in metrics),1)
        self.assertEqual(before,e.profile_digest(self.root))
        self.assertFalse(any(rel.startswith('s1-outcomes/') for rel in e.validate_pack(self.pack())[1]))
    def test_bind_sets_local_binding_and_missing_binding_is_friendly(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.base/'appdata')}):
            with self.assertRaises(ValueError) as ctx:
                e.profile_root(None)
            self.assertIn('bind', str(ctx.exception))
            result = e.bind(self.root)
            self.assertIn(result['status'], ('bound', 'unchanged'))
            self.assertEqual(e.profile_root(None), self.root)
            with self.assertRaises(ValueError):
                e.bind(self.target())
            second = self.target()
            self.assertEqual(e.bind(second, force=True)['status'], 'bound')
            self.assertEqual(e.profile_root(None), second)
    def test_read_payload_stdin_and_file(self):
        row = record()
        with patch('sys.stdin', io.StringIO(json.dumps(row))):
            parsed = e.read_payload('-')
        self.assertEqual(parsed, row)
        with self.assertRaises(FileNotFoundError):
            e.read_payload(str(self.base/'missing.json'))
    def test_read_payload_stdin_accepts_utf8_bom(self):
        row = record()
        with patch('sys.stdin', io.StringIO('\ufeff'+json.dumps(row))):
            self.assertEqual(e.read_payload('-'), row)
    def test_validate_record_lists_all_missing_fields(self):
        with self.assertRaises(ValueError) as cm:
            e.validate_record({'id':'1'*32,'component':'s1'})
        msg=str(cm.exception)
        for field in ('module','scope','category','state','text','task_id','created_at','evidence'):
            self.assertIn(field, msg)
    def test_query_multi_term_and_fuzzy(self):
        first = record(text='先给结论再给过程与依据', task_id='and-task')
        e.add(self.root, first)
        near = record(text='文档处理时先给目录和要点', task_id='fuzzy-task')
        e.add(self.root, near)
        hits = e.query(self.root, text='结论 过程')['records']
        self.assertTrue(any(r['id'] == first['id'] for r in hits))
        strict = e.query(self.root, text='文档时先给目录')['records']
        self.assertFalse(any(r['id'] == near['id'] for r in strict))
        fuzzy = e.query(self.root, text='文档时先给目录', fuzzy=True)['records']
        near_view = [r for r in fuzzy if r['id'] == near['id']]
        self.assertTrue(near_view)
        self.assertIn('fuzzy_score', near_view[0])
    def test_s2_environment_review_output(self):
        row = record('s2', environment={'os': 'nt', 'platform': 'win32',
                                        'python_version': '9.9.9', 'client': 'other-client'})
        e.add(self.root, row)
        view = e.query(self.root, component='s2')['records'][0]
        review = view['environment_review']
        self.assertEqual(review['current']['os'], os.name)
        self.assertIn('python_version', review['mismatched_keys'])
        self.assertIn('client', review['unverifiable_keys'])
        self.assertIn('reuse_notice', view)
    def test_query_exposes_cross_domain_pairs(self):
        e.add_event(self.root, event(preference_id='report', scope='work', topic='daily-report',
                                     text='Work report brief', module='documents'))
        e.add_event(self.root, event(preference_id='report', scope='personal', topic='daily-report',
                                     text='Personal report brief', module='life'))
        before = e.profile_digest(self.root)
        q = e.query(self.root)
        entry = next(item for item in q['cross_domain'] if item['topic'] == 'daily-report')
        self.assertEqual({x['scope'] for x in entry['entries']}, {'work', 'personal'})
        self.assertEqual(before, e.profile_digest(self.root))
    def test_overview_is_readonly_summary(self):
        e.add(self.root, record(state='confirmed', confirmed_by='synthetic yes', scope='work',
                                module='documents', task_id='overview-1'))
        e.add(self.root, record('s2', task_id='overview-2'))
        e.add_event(self.root, event(scope='work'))
        before = e.profile_digest(self.root)
        view = e.overview(self.root)
        self.assertEqual(before, e.profile_digest(self.root))
        self.assertEqual(len(view['confirmed_s1']), 1)
        self.assertEqual(len(view['s2_records']), 1)
        self.assertTrue(any(p['preference_id'] == 'brief' for p in view['preferences']))
    def test_consistency_check_reports_uncategorized_and_anchors(self):
        e.add_event(self.root, event(preference_id='brief', scope='work', text='Brief first'))
        good = e.add(self.root, record(module='uncategorized', category='待归类',
                                       text='锚点：work/brief', task_id='u-good'))
        bad = e.add(self.root, record('s2', module='uncategorized',
                                      text='锚点：personal/nope', task_id='u-bad'))
        report = e.consistency_check(self.root)
        self.assertEqual(len(report['uncategorized_records']), 2)
        anchors = {a['record_id']: a for a in report['anchors']}
        self.assertTrue(anchors[good['record_id']]['target_exists'])
        self.assertFalse(anchors[bad['record_id']]['target_exists'])
        self.assertIn(bad['record_id'], [m['record_id'] for m in report['missing_anchors']])
        self.assertFalse(report['ok'])

    def test_query_filters_and_retired_suggestions(self):
        for i in range(2):
            a=record(scope='personal',module='diary',task_id=str(i));e.add(self.root,a)
            e.add(self.root,record(scope='personal',module='diary',state='retired',supersedes=a['id']))
        e.add_event(self.root,event(scope='personal',module='diary',task_id='private'))
        e.add_event(self.root,event(source='general',scope='general',task_id='general'))
        q=e.query(self.root,scope='work',module='software')
        self.assertEqual(q['promotion_suggestions'],[])
        self.assertEqual([r['scope'] for r in q['effective_preferences']],['general'])
        q=e.query(self.root,scope='work',module='software',text='Brief')
        self.assertEqual([r['scope'] for r in q['events']],['general'])
        self.assertEqual(len(q['effective_preferences']),1)
        self.assertEqual(q['events'][0]['evidence_status']['authenticity'],'not-verified')
        q=e.query(self.root,task_id='general')
        self.assertEqual(q['effective_preferences'],[])
        self.assertEqual(len(q['related_preferences']),1)
    def test_promotion_confirmation_roundtrip_and_new_conflict(self):
        basis=[]
        for i in range(10):
            r=event(source='evidence:'+str(i),kind='support');basis.append(e.add_event(self.root,r)['event_id'])
        self.assertEqual(e.query(self.root)['effective_preferences'],[])
        with self.assertRaises(ValueError):e.add_event(self.root,event(source='p',kind='promote',basis=basis,confirmed_by=''))
        e.add_event(self.root,event(source='p',kind='promote',basis=basis))
        pref=e.query(self.root)['effective_preferences'][0]
        self.assertEqual((pref['tier'],pref['score']),('long-term',10))
        pack=self.pack(('s1',));target=self.target();plan=e.import_plan(target,pack)
        self.assertTrue(plan['rule_changes']['incoming_evidence'])
        e.import_pack(target,pack,plan['plan_id'])
        self.assertEqual(e.query(target)['effective_preferences'][0]['tier'],'long-term')
        e.add_event(self.root,event(source='conflict',kind='difference'))
        self.assertEqual(e.query(self.root)['effective_preferences'],[])
    def test_s2_unapplied_failure_and_conflicting_observations(self):
        lesson=record('s2');e.add(self.root,lesson)
        e.log_s2_outcome(self.root,outcome(lesson_id=lesson['id'],recurred=True))
        m=e.s2_metrics(self.root)['lessons'][0]
        self.assertEqual(m['unapplied_recurrence_tasks'],1)
        self.assertFalse(m['avoided_candidate'])
        e.log_s2_outcome(self.root,outcome(lesson_id=lesson['id'],recurred=False))
        m=e.s2_metrics(self.root)['lessons'][0]
        self.assertEqual(m['conflict_tasks'],['task-1'])
        self.assertEqual(m['opportunity_tasks'],0)
        other=record('s2');e.add(self.root,other)
        for t in ('a','b'):e.log_s2_outcome(self.root,outcome(task_id=t,lesson_id=other['id'],recalled=True))
        self.assertFalse(e.s2_metrics(self.root,other['id'])['lessons'][0]['avoided_candidate'])
    def test_s1_explicit_hit_legacy_and_conflicts(self):
        with self.assertRaises(ValueError):e.log_s1_outcome(self.root,s1outcome())
        e.add_event(self.root,event());e.log_s1_outcome(self.root,s1outcome())
        e.log_s1_outcome(self.root,s1outcome(hit=False,fewer_followups=False))
        m=e.s1_metrics(self.root)['metrics'][0]
        self.assertEqual(m['hit_count'],0);self.assertEqual(m['conflict_tasks'],['task-1'])
        legacy=s1outcome(task_id='legacy',schema=1)
        for k in ('opportunity','recalled','applied','hit'):legacy.pop(k)
        data=e.encoded(legacy);st.atomic_bytes(self.root/'s1-outcomes'/(st.digest(data)+'.json'),data)
        m=e.s1_metrics(self.root)['metrics'][0]
        self.assertEqual(m['unknown_hit_tasks'],1);self.assertEqual(m['hit_count'],0)
    def test_auxiliary_capacity_rejection_is_readable(self):
        lesson=record('s2');e.add(self.root,lesson);e.add_event(self.root,event())
        cases=[('s3-private',e.log_s3,dict(task_id='a',text='Synthetic',evidence='Synthetic'),e.query_s3),
               ('s2-outcomes',e.log_s2_outcome,outcome(task_id='a',lesson_id=lesson['id']),e.s2_metrics),
               ('s1-outcomes',e.log_s1_outcome,s1outcome(task_id='a'),e.s1_metrics)]
        for directory,write,row,query in cases:
            root=self.target()
            if directory=='s2-outcomes':e.add(root,lesson)
            if directory=='s1-outcomes':e.add_event(root,event())
            write(root,row);before=e.read(root/'profile.json');n=len(e.encoded(row))
            for limit in ({'MAX_FILES':1},{'MAX_TOTAL':n},{'MAX_FILE':n-1}):
                with self.subTest(directory=directory,limit=limit),patch.multiple(e,**limit):
                    with self.assertRaises(ValueError):write(root,{**row,'task_id':'b'})
            self.assertEqual(e.read(root/'profile.json'),before);query(root)
    def test_real_process_lock_contention_and_release(self):
        ready=self.base/'ready'
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import safe_store as st\nwith st.locked(Path(sys.argv[2])):\n Path(sys.argv[3]).write_text('ready')\n time.sleep(15)\n"
        proc=subprocess.Popen([sys.executable,'-B','-c',code,str(e.CORE/'scripts'),str(self.root),str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            end=time.monotonic()+8
            while not ready.exists() and proc.poll() is None and time.monotonic()<end:time.sleep(.02)
            self.assertTrue(ready.exists(),'Child did not acquire lock')
            with self.assertRaises(ValueError):e.add(self.root,record())
        finally:
            if proc.poll() is None:proc.terminate()
            proc.communicate(timeout=5)
        self.assertEqual(e.add(self.root,record())['status'],'added')
    def test_legacy_search_hash_and_limit(self):
        data=b'one needle\ntwo needle\n';path='legacy/sample.md'
        st.atomic_bytes(self.root/path,data)
        st.atomic_bytes(self.root/'legacy/index.json',e.encoded({'files':[{'path':path,'sha256':st.digest(data)}]}))
        q=e.legacy_search(self.root,'needle',limit=1)
        self.assertTrue(q['limit_reached']);self.assertEqual(q['matches'][0]['line'],1)
        st.atomic_bytes(self.root/path,b'changed')
        with self.assertRaises(ValueError):e.legacy_search(self.root,'needle')
    def test_decision_and_classification_evidence_paths(self):
        support=event(kind='support',classification_state='staged')
        sid=e.add_event(self.root,support)['event_id']
        e.add_event(self.root,event(source='classify',kind='classify',target=sid,basis=[sid],classification_state='confirmed',scope_target='personal',category_target='writing'))
        rows=e.load_rows(self.root);snap=e.pe.snapshot({Path(k).stem:r for k,r in rows.items()})
        self.assertEqual(snap['preferences'][0]['scope'],'personal')
        target=self.target();basis=[]
        for i in range(8):basis.append(e.add_event(target,event(source=str(i),kind='support'))['event_id'])
        diff=e.add_event(target,event(source='d',kind='difference'))['event_id'];basis.append(diff)
        e.add_event(target,event(source='decision',kind='decision',target=diff,basis=basis,choice='weaken',penalty=2))
        rows=e.load_rows(target);snap=e.pe.snapshot({Path(k).stem:r for k,r in rows.items()})
        self.assertEqual(snap['preferences'][0]['score'],6)

if __name__=='__main__':unittest.main()
