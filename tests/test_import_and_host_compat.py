"""Batch-2 regressions: D9 (silent empty-profile binding), D3 (zip packs),
D2 (host bookkeeping files), D6 (observe field errors)."""
from pathlib import Path
import json,os,sys,tempfile,unittest,zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
import core_package as cp
import safe_store as st
from test_components import record, test_review

class ZipPackImport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)
        e.add(self.root,record())

    def tearDown(self):
        self.tmp.cleanup()

    def export_zip(self,name='pack.zip',wrap=False):
        plan=e.export_plan(self.root,['s1'])
        out=self.base/name
        e.export_pack(self.root,out,['s1'],plan_id=plan['plan_id'],as_zip=True)
        if not wrap:
            return out
        wrapped=self.base/('wrapped-'+name)
        with zipfile.ZipFile(out) as src,zipfile.ZipFile(wrapped,'w') as dst:
            for item in src.infolist():
                dst.writestr('pack/'+item.filename,src.read(item))
        return wrapped

    def test_zip_pack_imports_like_a_directory_pack(self):
        pack=self.export_zip()
        man,rows=e.validate_pack(pack)
        self.assertTrue(rows)
        target=self.base/'target';e.init(target)
        plot=e.import_plan(target,pack,merge_into_current=True)
        result=e.import_pack(target,pack,plot['plan_id'],merge_into_current=True,
                             trust_reason='synthetic zip merge')
        self.assertTrue(result['added'])

    def test_single_wrapper_folder_inside_zip_is_unwrapped(self):
        pack=self.export_zip(name='wrapped.zip',wrap=True)
        man,rows=e.validate_pack(pack)
        self.assertTrue(rows)

    def test_unsafe_zip_entry_is_rejected(self):
        bad=self.base/'evil.zip'
        with zipfile.ZipFile(bad,'w') as z:
            z.writestr('pack.json','{}');z.writestr('../escape.json','{}')
        with self.assertRaises(ValueError):
            e.validate_pack(bad)

    def test_non_pack_path_gets_an_explicit_error(self):
        stray=self.base/'notes.txt';stray.write_text('not a pack',encoding='utf-8')
        with self.assertRaises(ValueError) as raised:
            e.validate_pack(stray)
        self.assertIn('pack',str(raised.exception).lower())

class EmptyProfileBinding(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.home=self.base/'data'
        self.profiles=self.home/'review-evolution'/'profiles'
        self.profiles.mkdir(parents=True)
        self.env=patch.dict(os.environ,{'LOCALAPPDATA':str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop();self.tmp.cleanup()

    def test_binding_an_empty_profile_warns_when_other_profiles_hold_data(self):
        used=self.profiles/'used';e.init(used);e.add(used,record())
        blank=self.profiles/'blank';e.init(blank)
        result=e.bind(str(blank))
        self.assertIn('notice',result)
        self.assertIn(str(used),result['notice'])
        self.assertEqual(e.profile_counts(blank)['total'],0)

    def test_binding_a_populated_profile_has_no_notice(self):
        used=self.profiles/'used';e.init(used);e.add(used,record())
        self.assertNotIn('notice',e.bind(str(used)))

    def test_context_binding_reports_the_same_warning(self):
        used=self.profiles/'used';e.init(used);e.add(used,record())
        blank=self.profiles/'blank';e.init(blank)
        result=e.bind_context(str(blank),'QwenWork','user-b')
        self.assertIn('notice',result)

class HostBookkeepingFiles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.core=self.base/'core'
        cp.export(e.CORE,self.core,test_review(e.CORE,self.base/'review.json'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_extra_file_is_still_core_tampering(self):
        (self.core/'leak.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError) as raised:
            cp.verify(self.core)
        self.assertIn('unexpected',str(raised.exception))

    def test_host_bookkeeping_file_is_classified_and_opt_in(self):
        (self.core/'_user_meta.json').write_text(json.dumps({'name':'wb-review-evolution'}),
                                                  encoding='utf-8')
        with self.assertRaises(ValueError) as raised:
            cp.verify(self.core)
        self.assertIn('host bookkeeping',str(raised.exception))
        self.assertTrue(cp.verify(self.core,allow_host_files=True)['files'])

    def test_host_file_rules_do_not_relax_missing_content(self):
        (self.core/'SKILL.md').unlink()
        (self.core/'_user_meta.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError) as raised:
            cp.verify(self.core,allow_host_files=True)
        self.assertIn('incomplete',str(raised.exception))

class ObserveFieldErrors(unittest.TestCase):
    def test_s2_outcome_error_lists_missing_fields(self):
        with self.assertRaises(ValueError) as raised:
            e.validate_outcome({'schema':1,'task_id':'t','lesson_id':'0'*32,'opportunity':True,
                                'recalled':True,'applied':True,'recurred':False})
        self.assertIn('evidence',str(raised.exception))

    def test_s1_outcome_error_lists_missing_fields(self):
        with self.assertRaises(ValueError) as raised:
            e.validate_s1_outcome({'schema':2,'task_id':'t','scope':'work','opportunity':True,
                                   'recalled':True,'applied':True,'hit':False})
        self.assertIn('fewer_followups',str(raised.exception))
