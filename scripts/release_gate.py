"""Read-only public-content gate. Findings contain hashes, never matched private text."""
import argparse
import json
from pathlib import Path
import re
import sys
import safe_store as st

ROOT_FILES={'SKILL.md','README.md','CHANGELOG.md','.gitignore','CORE.json','LICENSE'}
REFS={'workflow.md','record-schema.md','pack-format.md','install.md','installer-review-template.md',
      'preference-plan-a.md','task-start-checklist.md','release-check.md',
      'conversations/index.md','conversations/s2-hit-register.md','update-brief.md',
      'client-acceptance.md'}
SCRIPTS={'experience.py','preference_engine.py','safe_store.py','core_package.py','release_gate.py','release_update.py'}
TESTS={'test_components.py','test_release_gate.py','test_release_update.py'}
META_FIELDS={'version','release_series','data_schema','core_api','canonical_name','lineage_id','release_ready','files'}
DEV_VERSION=re.compile(r'0\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-beta(?:\.(?:0|[1-9][0-9]*))?)?\Z')
# Development core keeps the private identity; a content-bound public candidate may use
# the official public name while sharing the same lineage. Publication itself is never
# authorized by this gate.
ALLOWED_IDENTITIES=(
    ('wb-review-evolution','wb-review-evolution','development'),
    ('review-evolution','wb-review-evolution','public-release-candidate'),
)
ATTESTATIONS={'no_personal_history','no_private_authorizations','examples_are_synthetic','all_public_files_reviewed'}
# Pattern scanning is a supplement to file-by-file semantic review, not automatic anonymization.
PATTERNS={
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'absolute-windows-path':re.compile(r'\b[A-Za-z]:[\\/][^\s<>"\']+'),
    'absolute-user-path':re.compile(r'/(?:home|Users)/[^/\s<>"\']+(?:/[^\s<>"\']*)?'),
    'private-key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'access-token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})\b'),
    'assigned-secret':re.compile(r'''(?i)(?:api_key|password|access_token|client_secret)\s*[=:]\s*["'][A-Za-z0-9_+/=-]{12,}["']'''),
    'private-runtime-json':re.compile(r'''["'](?:profile_root|generated_by|device_id|repo_published_at)["']\s*:\s*["'][^"']+["']'''),
}
HARD={'private-key','access-token','assigned-secret','private-runtime-json','invalid-utf8','forbidden-path','invalid-metadata'}

def permitted(rel):
    st.relative(rel)
    if rel in ROOT_FILES:return True
    if rel.startswith('references/'):return rel[len('references/'):] in REFS
    if rel.startswith('scripts/'):return rel[len('scripts/'):] in SCRIPTS
    if rel.startswith('tests/'):return rel[len('tests/'):] in TESTS
    if rel in ('public-methods/README.md','public-methods/registry.json'):return True
    return re.fullmatch(r'public-methods/[a-z0-9][a-z0-9-]*\.md',rel) is not None

def finding(rel,rule,line,payload_digest,match=''):
    row={'file':rel,'rule':rule,'line':line,'file_sha256':payload_digest,'match_sha256':st.digest(match.encode())}
    row['id']=st.digest(st.json_bytes(row))
    return row

def scan_payload(payload):
    findings=[]
    for rel,data in payload.items():
        digest=st.digest(data)
        if not permitted(rel):findings.append(finding(rel,'forbidden-path',0,digest))
        try:text=data.decode('utf-8')
        except UnicodeDecodeError:
            findings.append(finding(rel,'invalid-utf8',0,digest));continue
        for num,line in enumerate(text.splitlines(),1):
            for rule,pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    findings.append(finding(rel,rule,num,digest,match.group()))
    try:
        meta=json.loads(payload['CORE.json'])
        if set(meta)!=META_FIELDS or meta['release_series']!='modular-1' or meta['data_schema']!=1 or meta['core_api']!=1:
            raise ValueError('Unknown metadata')
        if (meta['canonical_name'],meta['lineage_id']) not in {(a,b) for a,b,_ in ALLOWED_IDENTITIES}:
            raise ValueError('Unexpected identity')
        if not DEV_VERSION.fullmatch(meta['version']) or meta['release_ready'] is not False:
            raise ValueError('This development gate does not authorize v1 or public release')
        if set(meta['files'])!=set(payload)-{'CORE.json'}:
            raise ValueError('Payload inventory mismatch')
        if any(st.digest(payload[rel])!=digest for rel,digest in meta['files'].items()):
            raise ValueError('Metadata hash mismatch')
    except (KeyError,ValueError,TypeError):
        findings.append(finding('CORE.json','invalid-metadata',0,st.digest(payload.get('CORE.json',b''))))
    return {'schema':1,'files':{rel:st.digest(data) for rel,data in sorted(payload.items())},
            'findings':findings,'limits':'No pattern scanner proves absence of semantic privacy. An external, content-bound review is also required.'}

def load_payload(root):
    root=st.no_links(Path(root)).resolve()
    meta=json.loads((root/'CORE.json').read_text(encoding='utf-8'))
    paths=set(meta['files'])|{'CORE.json'}
    actual=set()
    for path in root.rglob('*'):
        st.no_links(path)
        if '__pycache__' in path.parts:continue
        if path.is_file():actual.add(path.relative_to(root).as_posix())
    if actual!=paths:raise ValueError('Unknown/missing core files')
    return {rel:st.inside(root,rel).read_bytes() for rel in sorted(paths)}

def scan(root):return scan_payload(load_payload(root))

def draft(root):
    report=scan(root)
    return {'schema':1,'purpose':'privacy-review-not-publication-authorization','state':'pending',
            'files':report['files'],'review_reference':'','attestations':{k:False for k in sorted(ATTESTATIONS)},
            'accepted_findings':{},'findings_to_review':report['findings']}

def check(payload,receipt):
    report=scan_payload(payload)
    if receipt.get('schema')!=1 or receipt.get('state')!='reviewed' or receipt.get('purpose')!='privacy-review-not-publication-authorization':
        raise ValueError('Missing completed content review')
    if receipt.get('files')!=report['files']:
        raise ValueError('Privacy review stale: file bytes changed')
    if not isinstance(receipt.get('review_reference'),str) or not receipt['review_reference'].strip():
        raise ValueError('Review needs an actual review reference')
    if receipt.get('attestations')!={k:True for k in ATTESTATIONS}:
        raise ValueError('Incomplete semantic/privacy review')
    accepted=receipt.get('accepted_findings',{})
    if not isinstance(accepted,dict) or any(not isinstance(v,str) or not v.strip() for v in accepted.values()):
        raise ValueError('Exceptions must explain exact synthetic/public findings')
    ids={f['id'] for f in report['findings']}
    if not set(accepted)<=ids:raise ValueError('Unknown/stale finding exception')
    if any(f['rule'] in HARD or f['id'] not in accepted for f in report['findings']):
        raise ValueError('Unresolved sensitive-content findings; inspect redacted scan report')
    return {'status':'privacy-gate-passed','files':len(payload),'findings_reviewed':len(accepted),
            'publication_authorized':False,'limits':report['limits']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('scan','draft','check'));p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--review',type=Path)
    a=p.parse_args()
    try:
        if a.command=='check':
            if a.review is None:p.error('--review required')
            result=check(load_payload(a.root),json.loads(st.no_links(a.review).read_text(encoding='utf-8')))
        else:result=scan(a.root) if a.command=='scan' else draft(a.root)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);raise SystemExit(1)
