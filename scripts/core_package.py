"""Verify/export exactly the development core manifest; never reads the profile."""
import argparse,json,hashlib,sys
from pathlib import Path
import safe_store as st
import release_gate as gate
ROOT=Path(__file__).resolve().parents[1]

def verify(root):
    root=st.no_links(Path(root)).resolve()
    meta=json.loads((root/'CORE.json').read_text(encoding='utf-8'))
    if meta.get('release_series')!='modular-1' or meta.get('data_schema')!=1:
        raise ValueError('Unsupported core metadata')
    files=meta['files']
    actual=set()
    for p in root.rglob('*'):
        st.no_links(p)
        if '__pycache__' in p.parts:
            continue
        if p.is_file():actual.add(p.relative_to(root).as_posix())
    if actual!=set(files)|{'CORE.json'}:
        raise ValueError('Core has unexpected/missing files: '+repr(actual ^ (set(files)|{'CORE.json'})))
    for rel,digest in files.items():
        if rel.startswith(('preferences/','legacy/','s1/','s2/','.wb-state/')):
            raise ValueError('Private/state path in core')
        if st.hash_file(st.inside(root,rel))!=digest:
            raise ValueError('Core content mismatch: '+rel)
    registry=json.loads((root/'public-methods/registry.json').read_text(encoding='utf-8'))
    allowed={'public-methods/README.md','public-methods/registry.json'}
    for method in registry['methods']:
        if method.get('state')!='approved' or not method.get('review_reference'):
            raise ValueError('Unreviewed public method')
        rel=method['file']
        if not rel.startswith('public-methods/') or files.get(rel)!=method['sha256']:
            raise ValueError('Method review not bound to content')
        allowed.add(rel)
    if {p for p in files if p.startswith('public-methods/')}!=allowed:
        raise ValueError('Unregistered method file')
    return {'version':meta['version'],'files':len(files),'sha256':st.hash_file(root/'CORE.json'),
            'release_ready':False,'note':'Development core; integrity is not a privacy/security certification.'}

def export(root,out,review=None):
    root=st.no_links(Path(root)).resolve();out=st.no_links(Path(out)).resolve()
    if out.exists() or root.is_relative_to(out) or out.is_relative_to(root):
        raise ValueError('Use a new directory outside core')
    result=verify(root)
    meta=json.loads((root/'CORE.json').read_text(encoding='utf-8'))
    # Capture checked bytes before writing anything; no data roots or bindings are loaded.
    payload={rel:st.inside(root,rel).read_bytes() for rel in meta['files']}
    if any(st.digest(b)!=meta['files'][rel] for rel,b in payload.items()):
        raise ValueError('Source changed')
    payload['CORE.json']=(root/'CORE.json').read_bytes()
    if st.digest(payload['CORE.json'])!=result['sha256']:
        raise ValueError('Manifest changed')
    if review is None:
        raise ValueError('Content-bound privacy review required before export')
    review=st.no_links(Path(review)).resolve()
    if review.is_relative_to(root) or review.is_relative_to(out):
        raise ValueError('Review receipt stays outside core/output')
    privacy=gate.check(payload,json.loads(review.read_text(encoding='utf-8')))
    for rel,b in payload.items():st.atomic_bytes(st.inside(out,rel),b)
    verify(out)
    result['privacy']=privacy
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','export'));parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path);parser.add_argument('--review',type=Path)
    args=parser.parse_args()
    if args.command=='export' and args.output is None:parser.error('--output required')
    try:print(json.dumps(verify(args.root) if args.command=='verify' else export(args.root,args.output,args.review)))
    except (ValueError,OSError,KeyError) as exc:print('ERROR: '+str(exc),file=sys.stderr);raise SystemExit(1)
