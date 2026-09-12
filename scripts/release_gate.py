"""Read-only public-content gate. Findings contain hashes, never matched private text."""
import argparse
import json
from pathlib import Path
import re
import sys
import safe_store as st

ROOT_FILES={'SKILL.md','README.md','CHANGELOG.md','KNOWN_ISSUES.md','.gitignore','CORE.json','LICENSE','runtime-policy.json','SECURITY.md'}
# 1.0 (2026-09-12): the repository hygiene files ship inside the published content, so the
# git tag tree, the public candidate and the install package stay byte-identical.
GITHUB_FILES={'ISSUE_TEMPLATE/bug_report.yml','ISSUE_TEMPLATE/feature_request.yml','ISSUE_TEMPLATE/config.yml'}
REFS={'s3-issues.md','workflow.md','record-schema.md','pack-format.md','install.md','installer-review-template.md',
      'preference-plan-a.md','task-start-checklist.md','release-check.md',
      'conversations/index.md','conversations/s2-hit-register.md','update-brief.md',
      'client-acceptance.md','compatibility-matrix.md','feedback-template.md',
      'host-integration.md'}
SCRIPTS={'optional_features.py','s3_optional.py','build_public.py','recall_view.py','diagnostics.py','profile_backup.py','experience.py','preference_engine.py','safe_store.py','core_package.py','release_gate.py','release_update.py','check_windows_launchers.py','re-cli.ps1','verify-core.ps1'}
TESTS={'test_optional_s3.py','test_s2_classification.py','test_recall_view.py','test_diagnostics.py','test_profile_backup.py','test_components.py','test_release_gate.py','test_release_update.py','test_archive_reminder.py','test_windows_launchers.py','test_export_robustness.py','test_import_and_host_compat.py','test_docs_consistency.py','test_recall_relaxed.py','test_release_readiness.py','test_candidate_fallback.py','test_candidate_reminder.py','test_skill_metadata.py','test_trigger_evals.py','test_install_entry.py','test_human_view.py','test_upgrade_recovery.py'}
EVALS=re.compile(r'[a-z0-9][a-z0-9._-]*\.json\Z')
# tests/__init__.py lets the suite be discovered from outside the skill root (U8).
TEST_HELPERS={'__init__.py'}
META_FIELDS={'version','release_series','data_schema','core_api','canonical_name','lineage_id','release_ready','files'}
DEV_VERSION=re.compile(r'0\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-beta(?:\.(?:0|[1-9][0-9]*))?)?\Z')
# 1.0-A (2026-09-12): a stable release is a different channel, not a bigger number.
# Stable = major >= 1 with no prerelease suffix, and it must carry evidence the beta
# channel never needed: test evidence, real acceptance evidence, a frozen manifest hash
# bound to this exact CORE.json, and the user's two recorded confirmations.
STABLE_VERSION=re.compile(r'(?:1|[2-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z')
STABLE_EVIDENCE_REFERENCES=('tests_evidence','acceptance_evidence')
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
HARD={'private-key','access-token','assigned-secret','private-runtime-json','invalid-utf8','forbidden-path','invalid-metadata','stable-evidence-invalid'}

def permitted(rel):
    st.relative(rel)
    if rel in ROOT_FILES:return True
    if rel.startswith('.github/'):return rel[len('.github/'):] in GITHUB_FILES
    if rel.startswith('references/'):return rel[len('references/'):] in REFS
    if rel.startswith('scripts/'):return rel[len('scripts/'):] in SCRIPTS
    if rel.startswith('tests/evals/'):return EVALS.match(rel[len('tests/evals/'):]) is not None
    if rel.startswith('tests/'):return rel[len('tests/'):] in TESTS or rel[len('tests/'):] in TEST_HELPERS
    if rel in ('public-methods/README.md','public-methods/registry.json'):return True
    return re.fullmatch(r'public-methods/[a-z0-9][a-z0-9-]*\.md',rel) is not None

def finding(rel,rule,line,payload_digest,match=''):
    row={'file':rel,'rule':rule,'line':line,'file_sha256':payload_digest,'match_sha256':st.digest(match.encode())}
    row['id']=st.digest(st.json_bytes(row))
    return row

def stable_evidence_problems(payload,receipt):
    """Problems that block a stable release. Only the frozen hash is machine-checkable;
    the two references and the confirmation count are named evidence a reviewer signs."""
    if receipt is None:
        return ['stable-evidence-required']
    evidence=receipt.get('stable_evidence')
    if not isinstance(evidence,dict):
        return ['stable_evidence block missing from the review receipt']
    problems=[]
    for key in STABLE_EVIDENCE_REFERENCES:
        value=evidence.get(key)
        if not isinstance(value,str) or not value.strip():
            problems.append(key+' reference missing')
    if evidence.get('frozen_core_sha256')!=st.digest(payload.get('CORE.json',b'')):
        problems.append('frozen_core_sha256 does not match this CORE.json')
    if evidence.get('confirmations')!=2:
        problems.append('confirmations must be exactly 2 (the two-confirmation rule)')
    return problems

def scan_payload(payload,receipt=None):
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
    meta=None
    try:
        meta=json.loads(payload['CORE.json'])
        if set(meta)!=META_FIELDS or meta['release_series']!='modular-1' or meta['data_schema']!=1 or meta['core_api']!=1:
            raise ValueError('Unknown metadata')
        if (meta['canonical_name'],meta['lineage_id']) not in {(a,b) for a,b,_ in ALLOWED_IDENTITIES}:
            raise ValueError('Unexpected identity')
        if DEV_VERSION.fullmatch(meta['version']):
            if meta['release_ready'] is not False:
                raise ValueError('A development/beta core must keep release_ready false')
        elif STABLE_VERSION.fullmatch(meta['version']):
            if meta['release_ready'] is not True:
                raise ValueError('A stable version requires release_ready true')
        else:
            raise ValueError('This gate does not authorize that version scheme')
        if set(meta['files'])!=set(payload)-{'CORE.json'}:
            raise ValueError('Payload inventory mismatch')
        if any(st.digest(payload[rel])!=digest for rel,digest in meta['files'].items()):
            raise ValueError('Metadata hash mismatch')
    except (KeyError,ValueError,TypeError):
        meta=None
        findings.append(finding('CORE.json','invalid-metadata',0,st.digest(payload.get('CORE.json',b''))))
    if meta is not None and STABLE_VERSION.fullmatch(meta['version']):
        problems=stable_evidence_problems(payload,receipt)
        if problems:
            rule='stable-evidence-required' if problems==['stable-evidence-required'] else 'stable-evidence-invalid'
            findings.append(finding('CORE.json',rule,0,st.digest(payload.get('CORE.json',b''))))
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
    receipt={'schema':1,'purpose':'privacy-review-not-publication-authorization','state':'pending',
             'files':report['files'],'review_reference':'','attestations':{k:False for k in sorted(ATTESTATIONS)},
             'accepted_findings':{},'findings_to_review':report['findings']}
    meta=json.loads((st.no_links(Path(root)).resolve()/'CORE.json').read_text(encoding='utf-8'))
    if STABLE_VERSION.fullmatch(meta.get('version','')):
        receipt['stable_evidence']={'tests_evidence':'','acceptance_evidence':'',
                                    'frozen_core_sha256':'','confirmations':0}
    return receipt

def check(payload,receipt):
    report=scan_payload(payload,receipt)
    if receipt.get('schema')!=1 or receipt.get('state')!='reviewed' or receipt.get('purpose')!='privacy-review-not-publication-authorization':
        raise ValueError('Missing completed content review')
    if receipt.get('files')!=report['files']:
        raise ValueError('Privacy review stale: file bytes changed')
    if not isinstance(receipt.get('review_reference'),str) or not receipt['review_reference'].strip():
        raise ValueError('Review needs an actual review reference')
    if receipt.get('attestations')!={k:True for k in ATTESTATIONS}:
        raise ValueError('Incomplete semantic/privacy review')
    try:
        version=json.loads(payload['CORE.json']).get('version','')
    except (KeyError,ValueError,TypeError):
        version=''
    if STABLE_VERSION.fullmatch(version):
        problems=[p for p in stable_evidence_problems(payload,receipt) if p!='stable-evidence-required']
        if problems:
            raise ValueError('Stable release evidence incomplete: '+'; '.join(problems))
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
