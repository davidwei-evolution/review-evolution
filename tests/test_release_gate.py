from pathlib import Path
import sys,unittest,tempfile,json,os,uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import release_gate as g
import core_package as cp
import safe_store as st
from test_components import test_review

def payload(text='Public content',extra=None,metadata=None):
    data={'README.md':text.encode()}
    data.update(extra or {})
    meta=dict(version='0.9.1',release_series='modular-1',data_schema=1,core_api=1,
              canonical_name='wb-review-evolution',lineage_id='wb-review-evolution',release_ready=False,
              files={k:st.digest(v) for k,v in data.items()})
    meta.update(metadata or {})
    data['CORE.json']=st.json_bytes(meta);return data

def receipt(data):
    return dict(schema=1,purpose='privacy-review-not-publication-authorization',state='reviewed',
                files={k:st.digest(v) for k,v in data.items()},review_reference='Synthetic reviewer',
                attestations={k:True for k in g.ATTESTATIONS},accepted_findings={})

class Gate(unittest.TestCase):
    def test_pattern_probes_blocked_and_logs_redacted(self):
        probes=['person'+'@'+'example.invalid', 'D'+':\\Private\\client', '/home/'+'synthetic/private',
                '/Users/'+'synthetic/private','gh'+'p_'+'a'*36,
                '-----BEGIN '+'PRIVATE KEY-----','password = '+'"'+'a'*20+'"']
        for value in probes:
            with self.subTest(value_length=len(value)):
                data=payload(value);report=g.scan_payload(data)
                self.assertTrue(report['findings'])
                self.assertNotIn(value,json.dumps(report))
                with self.assertRaises(ValueError):g.check(data,receipt(data))
    def test_private_project_name_needs_manual_attestation(self):
        data=payload('Internal project '+uuid.uuid4().hex)
        r=receipt(data);r['attestations']['no_personal_history']=False
        with self.assertRaises(ValueError):g.check(data,r)
    def test_unknown_and_private_files_rejected_even_if_in_manifest(self):
        for name in ('preferences/events/private.json','references/conversations/documents/records.md','references/arbitrary-case.md','s3-private/case.json','installation.json'):
            with self.subTest(name=name):
                data=payload(extra={name:b'private'})
                with self.assertRaises(ValueError):g.check(data,receipt(data))
    def test_device_and_time_metadata_rejected(self):
        for key in ('device_id','generated_by','generated_at','profile_id'):
            data=payload(metadata={key:'synthetic'})
            with self.assertRaises(ValueError):g.check(data,receipt(data))
    def test_changed_content_invalidates_review(self):
        a=payload('One');b=payload('Two')
        with self.assertRaises(ValueError):g.check(b,receipt(a))
    def test_exact_synthetic_exception_expires_on_change(self):
        a=payload('sample'+'@'+'example.invalid');r=receipt(a)
        f=g.scan_payload(a)['findings'][0];r['accepted_findings'][f['id']]='Synthetic documentation example'
        self.assertEqual(g.check(a,r)['status'],'privacy-gate-passed')
        b=payload('other'+'@'+'example.invalid')
        with self.assertRaises(ValueError):g.check(b,r)
    def test_secret_findings_cannot_be_waived(self):
        data=payload('gh'+'p_'+'a'*36);r=receipt(data)
        r['accepted_findings']={f['id']:'attempted exception' for f in g.scan_payload(data)['findings']}
        with self.assertRaises(ValueError):g.check(data,r)
    def test_export_without_review_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out'
            with self.assertRaises(ValueError):cp.export(cp.ROOT,out)
            self.assertFalse(out.exists())
    def test_export_independent_of_host_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);r=test_review(cp.ROOT,tmp/'review.json')
            with patch.dict(os.environ,{'WB_DEVICE_ID':'synthetic-first','USERNAME':'synthetic-one'}):cp.export(cp.ROOT,tmp/'a',r)
            with patch.dict(os.environ,{'WB_DEVICE_ID':'synthetic-second','USERNAME':'synthetic-two'}):cp.export(cp.ROOT,tmp/'b',r)
            a={p.relative_to(tmp/'a').as_posix():p.read_bytes() for p in (tmp/'a').rglob('*') if p.is_file()}
            b={p.relative_to(tmp/'b').as_posix():p.read_bytes() for p in (tmp/'b').rglob('*') if p.is_file()}
            self.assertEqual(a,b)
            self.assertFalse((tmp/'a'/'review.json').exists())
    def test_invalid_utf8_and_unknown_metadata_fail_closed(self):
        data=payload(extra={'SKILL.md':bytes([255])})
        with self.assertRaises(ValueError):g.check(data,receipt(data))
        data=payload(metadata={'notes':'unknown'})
        with self.assertRaises(ValueError):g.check(data,receipt(data))
    def test_public_candidate_identity_accepted_unknown_rejected(self):
        data=payload(metadata={'canonical_name':'review-evolution'})
        report=g.scan_payload(data)
        self.assertFalse(any(f['rule']=='invalid-metadata' for f in report['findings']))
        self.assertEqual(g.check(data,receipt(data))['status'],'privacy-gate-passed')
        for meta in ({'canonical_name':'other','lineage_id':'wb-review-evolution'},
                     {'canonical_name':'review-evolution','lineage_id':'other'}):
            bad=payload(metadata=meta)
            with self.assertRaises(ValueError):g.check(bad,receipt(bad))
    def test_v1_release_still_blocked_by_dev_gate(self):
        data=payload(metadata={'version':'1.0.0','canonical_name':'review-evolution'})
        with self.assertRaises(ValueError):g.check(data,receipt(data))
    def test_beta_prerelease_version_accepted_by_dev_gate(self):
        data=payload(metadata={'version':'0.15.0-beta.1','canonical_name':'review-evolution'})
        report=g.scan_payload(data)
        self.assertFalse(any(f['rule']=='invalid-metadata' for f in report['findings']))
        self.assertEqual(g.check(data,receipt(data))['status'],'privacy-gate-passed')

if __name__=='__main__':unittest.main()
