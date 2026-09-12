"""Regression cover for KNOWN_ISSUES D1: an event carrying a field outside the schema
(a redundant component in particular) must never break plan-export or export."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import experience as e
import preference_engine as pe
import safe_store as st
from test_components import record, event

def legacy_event(**kw):
    """An event shaped the way a looser/older writer produced it (extra component)."""
    row=event(preference_id='legacy-component',module='documents')
    row['component']='s1'
    row.update(kw)
    return row

def write_legacy_event(root,row=None):
    row=legacy_event() if row is None else row
    key=pe.event_id(row)
    st.atomic_bytes(root/'preferences'/'events'/(key+'.json'),st.json_bytes(row))
    return key

class ExportRobustness(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'profile';e.init(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_plans_survive_a_redundant_component_on_an_event(self):
        e.add(self.root,record())
        write_legacy_event(self.root)
        for components in (['s1'],['s2'],['s1','s2']):
            for kwargs in ({},{'scope':'work'},{'scope':'personal'},{'module':'documents'}):
                with self.subTest(components=components,**kwargs):
                    self.assertIn('plan_id',e.export_plan(self.root,components,**kwargs))
        self.assertTrue(e.export_plan(self.root,['s1'])['files'])

    def test_export_pack_and_import_round_trip_with_legacy_event(self):
        e.add(self.root,record())
        write_legacy_event(self.root)
        plan=e.export_plan(self.root,['s1'])
        pack=self.base/'pack'
        e.export_pack(self.root,pack,['s1'],plan_id=plan['plan_id'])
        target=self.base/'target';e.init(target)
        preview=e.import_plan(target,pack,merge_into_current=True)
        first=e.import_pack(target,pack,preview['plan_id'],merge_into_current=True,
                            trust_reason='synthetic merge test')
        self.assertTrue(first['added'])
        self.assertTrue(e.export_plan(target,['s1'])['files'])
        second=e.import_plan(target,pack,merge_into_current=True)
        repeat=e.import_pack(target,pack,second['plan_id'],merge_into_current=True,
                             trust_reason='synthetic merge test')
        self.assertEqual(repeat.get('added',0),0)

    def test_add_event_strips_fields_outside_the_schema(self):
        result=e.add_event(self.root,legacy_event())
        self.assertEqual(result['status'],'added')
        self.assertEqual(result.get('dropped_fields'),['component'])
        stored=json.loads((self.root/'preferences'/'events'/
                           (result['event_id']+'.json')).read_text(encoding='utf-8'))
        self.assertNotIn('component',stored)
        self.assertEqual(pe.load(self.root)[result['event_id']],stored)

    def test_resubmitting_an_event_over_legacy_stored_data_is_idempotent(self):
        write_legacy_event(self.root)
        self.assertEqual(e.add_event(self.root,legacy_event())['status'],'unchanged')

    def test_wrong_component_value_is_still_rejected(self):
        bad=legacy_event();bad['component']='s2'
        with self.assertRaises(ValueError):
            e.add_event(self.root,bad)
