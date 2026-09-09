from pathlib import Path
import json,os,sys,tempfile,unittest,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import experience as e
import safe_store as st
import profile_backup as cw
from test_components import record,event,s1outcome,outcome


class ProfileBackup(unittest.TestCase):
    def test_empty_directories_and_all_auxiliary_files_preserved(self):
        (self.root/'legacy/empty').mkdir(parents=True)
        lesson=record('s2');e.add(self.root,lesson)
        e.log_s2_outcome(self.root,outcome(lesson_id=lesson['id']))
        e.add_trusted_source(self.root,'a'*32,'synthetic ownership confirmation')
        e.log_s3(self.root,{'task_id':'synthetic','text':'iteration','evidence':'synthetic'})
        e.mark_updates(self.root,{'channel':'repo','checked_at':'2026-09-06T00:00:00Z','summary':'synthetic','repo_status':'repo_ready','new_items':0})
        backup=self.make_backup();target=self.base/'restored'
        plan=cw.restore_plan(backup,target);cw.restore(backup,target,plan['plan_id'])
        self.assertEqual(cw.directories(self.root),cw.directories(target))
        self.assertEqual(cw.inventory(self.root)[0],cw.inventory(target)[0])
        self.assertEqual(e.s2_metrics(self.root),e.s2_metrics(target))
        self.assertEqual(e.trusted_sources_view(self.root),e.trusted_sources_view(target))

    def test_hardlink_rejected(self):
        outside=self.base/'outside';outside.write_bytes(b'synthetic')
        os.link(outside,self.root/'linked')
        with self.assertRaises(ValueError):cw.backup_plan(self.root)

    def test_writer_lock_contention_refuses_backup(self):
        plan=cw.backup_plan(self.root)
        with st.locked(self.root):
            with self.assertRaises(ValueError):cw.backup(self.root,self.base/'backup',plan['plan_id'])

    def test_core_destination_extra_lock_and_manifest_flags_rejected(self):
        with self.assertRaises(ValueError):cw.separate_new_target(self.root,e.CORE/'private-backup')
        backup=self.make_backup()
        st.atomic_bytes(backup/'data/.wb-state/lock',b'x')
        with self.assertRaisesRegex(ValueError,'volatile lock'):cw.validate_backup(backup)

    def test_mutation_during_validation_and_restore_failure(self):
        backup=self.make_backup();original=cw.checked_profile
        def mutate(root):
            original(root)
            if root==backup/'data':st.atomic_bytes(root/'legacy/changed.txt',b'changed')
        with patch.object(cw,'checked_profile',side_effect=mutate):
            with self.assertRaises(ValueError):cw.validate_backup(backup)

    def test_restore_write_failure_never_publishes_target(self):
        backup=self.make_backup();target=self.base/'new';plan=cw.restore_plan(backup,target)
        before=self.snapshot()
        with patch.object(st,'atomic_bytes',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):cw.restore(backup,target,plan['plan_id'])
        self.assertFalse(target.exists());self.assertEqual(before,self.snapshot())
        cw.validate_backup(backup)

    def test_target_race_does_not_overwrite(self):
        target=self.base/'new'
        def writer(stage):
            target.mkdir();(target/'keep').write_bytes(b'keep')
        with self.assertRaises(ValueError):cw.publish_directory(target,writer)
        self.assertEqual((target/'keep').read_bytes(),b'keep')

    def test_cli_unbound_restore_and_failure_exit(self):
        backup=self.make_backup();target=self.base/'restored'
        env=dict(os.environ,LOCALAPPDATA=str(self.base/'unbound'))
        command=[sys.executable,'-B',str(e.CORE/'scripts/experience.py')]
        def run(*args):return subprocess.run(command+list(args),env=env,capture_output=True,encoding='utf-8')
        checked=run('check-backup',str(backup));self.assertEqual(checked.returncode,0,checked.stderr)
        plan=run('plan-restore',str(backup),str(target));self.assertEqual(plan.returncode,0,plan.stderr)
        result=run('restore',str(backup),str(target),'--plan-id',json.loads(plan.stdout)['plan_id'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.base/'unbound/review-evolution/installation.json').exists())
        failed=run('restore',str(backup),str(target),'--plan-id','bad')
        self.assertNotEqual(failed.returncode,0);self.assertNotIn('RESTORED',failed.stdout)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)


    def tearDown(self):self.tmp.cleanup()


    def snapshot(self):return cw.inventory(self.root)[0]


    def make_backup(self):
        target=self.base/'backup';plan=cw.backup_plan(self.root)
        cw.backup(self.root,target,plan['plan_id']);return target


    def test_complete_backup_restore_preserves_auxiliary_and_binding(self):
        e.add_event(self.root,event());e.add(self.root,record())
        e.log_s3(self.root,{'task_id':'synthetic','text':'Synthetic iteration','evidence':'Synthetic'})
        e.log_s1_outcome(self.root,s1outcome())
        st.atomic_bytes(self.root/'legacy/note.txt',b'Synthetic preserved archive')
        before=self.snapshot();backup=self.make_backup();target=self.base/'restored'
        plan=cw.restore_plan(backup,target)
        with patch.object(e,'bind',side_effect=AssertionError('Binding changed')):
            result=cw.restore(backup,target,plan['plan_id'])
        self.assertEqual(result['status'],'RESTORED')
        self.assertEqual(before,cw.inventory(target)[0]);self.assertEqual(before,self.snapshot())
        self.assertEqual(e.query(self.root),e.query(target))
        self.assertEqual(e.query_s3(self.root),e.query_s3(target))


    def test_backup_plan_is_readonly_stale_pending_and_capacity_rejected(self):
        before=self.snapshot();plan=cw.backup_plan(self.root);self.assertEqual(before,self.snapshot())
        e.add(self.root,record())
        with self.assertRaisesRegex(ValueError,'Stale'):cw.backup(self.root,self.base/'backup',plan['plan_id'])
        with patch.object(st,'pending',return_value=['x']):
            with self.assertRaises(ValueError):cw.backup_plan(self.root)
        with patch.object(cw,'BACKUP_TOTAL',1):
            with self.assertRaises(ValueError):cw.backup_plan(self.root)


    def test_backup_changes_and_failed_write_not_published(self):
        plan=cw.backup_plan(self.root);target=self.base/'backup';before=self.snapshot()
        original=st.atomic_bytes
        def fail(path,data,*args,**kwargs):
            if Path(path).name=='backup.json':raise OSError('disk full')
            return original(path,data,*args,**kwargs)
        with patch.object(st,'atomic_bytes',side_effect=fail):
            with self.assertRaises(OSError):cw.backup(self.root,target,plan['plan_id'])
        self.assertFalse(target.exists());self.assertEqual(before,self.snapshot())


    def test_restore_refuses_tamper_existing_overlap_and_wrong_reader(self):
        backup=self.make_backup();target=self.base/'restored'
        with self.assertRaises(ValueError):cw.restore_plan(backup,self.root)
        with self.assertRaises(ValueError):cw.restore_plan(backup,backup/'nested')
        manifest=e.read(backup/'backup.json');manifest['reader_core']='0'*64
        manifest['backup_id']=st.digest(st.json_bytes({k:v for k,v in manifest.items() if k!='backup_id'}))
        (backup/'backup.json').write_bytes(st.json_bytes(manifest))
        with self.assertRaisesRegex(ValueError,'Different reader'):cw.restore_plan(backup,target)


    def test_restore_content_tamper_and_stale_plan(self):
        backup=self.make_backup();target=self.base/'restored';plan=cw.restore_plan(backup,target)
        with self.assertRaisesRegex(ValueError,'Stale'):cw.restore(backup,target,'invalid')
        (backup/'data/profile.json').write_text('{}')
        with self.assertRaises(ValueError):cw.restore(backup,target,plan['plan_id'])
        self.assertFalse(target.exists())

