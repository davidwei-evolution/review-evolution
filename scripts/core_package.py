"""Verify/export exactly the development core manifest; never reads the profile."""
import argparse,json,hashlib,re,sys
from pathlib import Path
import safe_store as st
import release_gate as gate
ROOT=Path(__file__).resolve().parents[1]

# Files some hosts/OSes drop into any directory they touch. They are not core content,
# but they are still refused unless the caller opts in (see KNOWN_ISSUES D2).
HOST_BOOKKEEPING_FILES={'_user_meta.json','.ds_store','thumbs.db','desktop.ini'}
HOST_BOOKKEEPING_DIRS={'.idea','.vscode'}

# U1 (2026-09-12): a client's upload/register path can rewrite an installed file
# (seen: SKILL.md frontmatter `description: >` turned into `description: |` plus an
# injected `install_method:` key). Integrity must still refuse silently-accepted edits,
# but the error has to say what to do next - the fix is to restore the original file,
# never to bend the manifest.
HOST_REWRITE_HINT=(
    '若该文件是被客户端“上传/注册”路径改写的（例如 frontmatter 的 `description: >` 变成 `description: |`，'
    '或多出 `install_method:` 之类的字段），处置是：**备份该文件 → 用同版本原包里的同名文件复原 → 重新 verify**；'
    '**不要修改 CORE.json 去迁就它**。只读诊断：python -B scripts/core_package.py diff --root <技能目录>'
    '（加 --reference <同版本原包目录> 可给出“是否仅表示法差异”的结论）。')

def _normalize_lines(data):
    text=data.decode('utf-8').lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n')
    return [line.rstrip() for line in text.split('\n')]

def _frontmatter_split(lines):
    if not lines or lines[0].strip()!='---':
        return None,lines
    for index in range(1,len(lines)):
        if lines[index].strip()=='---':
            return lines[1:index],lines[index+1:]
    return None,lines

# A real frontmatter key line starts at column 0 with an identifier and a colon. Anything
# indented is a value (block scalar content) - never a key.
FRONTMATTER_KEY=re.compile(r'[A-Za-z_][A-Za-z0-9_-]*:.*')

def _key_names(lines):
    """N2 (2026-09-12, completed): return only genuine `key:` names, in order.

    The earlier half-fix cleaned `facts.frontmatter_keys` but left `keys_added`/`keys_removed`
    on the loose `line.split(':',1)[0].strip()` path, whose `.strip()` erased the indentation
    check - a flattened host rewrite then reported a 355-character Chinese paragraph as a
    "key name". Both sets now go through this single filter.
    """
    return [line.split(':',1)[0] for line in lines if FRONTMATTER_KEY.fullmatch(line)]

def _file_facts(path,reference=None):
    """Read-only facts about a file that does not match the manifest.

    Without a reference we can only describe the file; with the same-version original we
    can classify the difference (representation-only vs body change). Nothing here edits
    anything, and no file content is printed.
    """
    data=path.read_bytes()
    facts={'bytes':len(data),'utf8_bom':data.startswith(b'\xef\xbb\xbf')}
    try:
        lines=_normalize_lines(data)
    except UnicodeDecodeError:
        return {'kind':'binary-or-non-utf8','facts':facts}
    head,body=_frontmatter_split(lines)
    facts['crlf_present']=b'\r\n' in data
    if head is not None:
        keys=_key_names(head)
        styles=[line.split(':',1)[1].strip() for line in head if ':' in line
                and line.split(':',1)[1].strip() in ('>','>-','|','|-')]
        facts['frontmatter_keys']=keys
        facts['frontmatter_block_styles']=styles
        facts['body_lines']=len(body)
    if reference is None:
        # Intrinsic hint only; a real classification needs the original bytes.
        hint=bool(head is not None and facts['frontmatter_keys'])
        return {'kind':'unknown-needs-reference','likely_frontmatter_edited':hint,'facts':facts}
    original=_normalize_lines(reference.read_bytes())
    if original==lines:
        return {'kind':'representation-only','facts':facts,
                'note':'规范化行尾/BOM/行尾空白后与原件一致'}
    old_head,old_body=_frontmatter_split(original)
    if old_head is not None and head is not None and old_body==body:
        old_keys=set(_key_names(old_head))
        new_keys=set(_key_names(head))
        return {'kind':'frontmatter-only','facts':facts,
                'keys_added':sorted(new_keys-old_keys),'keys_removed':sorted(old_keys-new_keys),
                'note':'正文与原件一致，差异只在 frontmatter 表示法/字段'}
    return {'kind':'body-differs','facts':facts,'note':'正文本身与原件不同，不是纯表示法差异'}

def diff(root,reference=None):
    """Read-only diagnosis: list every file that does not match the manifest."""
    root=st.no_links(Path(root)).resolve()
    meta=json.loads((root/'CORE.json').read_text(encoding='utf-8'))
    reference=st.no_links(Path(reference)).resolve() if reference else None
    differences=[];missing=[]
    for rel,digest in sorted(meta['files'].items()):
        path=st.inside(root,rel)
        if not path.is_file():
            missing.append(rel);continue
        data=path.read_bytes()
        if st.digest(data)==digest:
            continue
        reference_path=st.inside(reference,rel) if reference is not None and (reference/rel).is_file() else None
        row={'file':rel,'actual_sha256':st.digest(data),'expected_sha256':digest}
        row.update(_file_facts(path,reference_path))
        differences.append(row)
    expected=set(meta['files'])|{'CORE.json'}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}
    extra=sorted(actual-expected)
    status='MATCH' if not differences and not missing and not extra else 'MISMATCH'
    result={'status':status,'root':str(root),'files_checked':len(meta['files']),
            'differences':differences,'missing':missing,'extra_files':extra,'read_only':True}
    if status=='MISMATCH':
        result['next_step']=HOST_REWRITE_HINT
    return result

def host_bookkeeping(rel):
    parts=[part.casefold() for part in Path(rel).parts]
    if not parts:
        return False
    if parts[-1] in HOST_BOOKKEEPING_FILES:
        return True
    return any(part in HOST_BOOKKEEPING_DIRS for part in parts[:-1])

def verify(root,allow_host_files=False,tolerate=()):
    """tolerate: 只读列出允许“与自身清单不符”的文件（宿主改写修复用，默认空集）。

    默认行为不变：任何内容不符都直接拒绝。传入 tolerate 时这些文件仍会被**如实报告**在
    `tolerated_mismatches` 里，由调用方决定是否用可信来源的同名文件覆盖；本函数不写盘。
    """
    root=st.no_links(Path(root)).resolve()
    tolerate=set(tolerate or ())
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
    expected=set(files)|{'CORE.json'}
    missing=sorted(expected-actual)
    if missing:
        raise ValueError('Core is incomplete; missing files: '+repr(missing))
    extra=sorted(actual-expected)
    if extra:
        host=sorted(rel for rel in extra if host_bookkeeping(rel))
        unknown=sorted(set(extra)-set(host))
        if unknown:
            raise ValueError('Core has unexpected files: '+repr(unknown)+
                             '; these are not host bookkeeping files, so they are treated as core tampering. '
                             'Keep the core directory exclusive to this skill.')
        if not allow_host_files:
            raise ValueError('Core has host bookkeeping files: '+repr(host)+
                             '; the host or OS wrote them into the skill directory. Core content itself is unchanged, '
                             'but integrity checks refuse extra files by default. Rerun with --allow-host-files to accept '
                             'them, or keep the core directory exclusive.')
    mismatched=[]
    for rel,digest in files.items():
        if rel.startswith(('preferences/','legacy/','s1/','s2/','.wb-state/')):
            raise ValueError('Private/state path in core')
        if st.hash_file(st.inside(root,rel))!=digest:
            if rel in tolerate:
                mismatched.append(rel)
                continue
            # U1: keep the stable wording, add what to do about a host-rewritten file.
            raise ValueError('Core content mismatch: '+rel+' | '+HOST_REWRITE_HINT)
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
    ready=meta.get('release_ready') is True
    result={'version':meta['version'],'files':len(files),'sha256':st.hash_file(root/'CORE.json'),
            'release_ready':ready,
            'note':('Released core; integrity is not a privacy/security certification.'
                    if ready else
                    'Development core; integrity is not a privacy/security certification.')}
    if mismatched:
        result['tolerated_mismatches']=sorted(mismatched)
    return result

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

def reseal(root,version=None):
    """Development-loop entry: rewrite CORE.json from the files that are actually there.

    Editing a manifest-bound file invalidates the core, so tests then fail in bulk with
    'Core content mismatch'. The fix is to reseal, not to weaken verification.
    """
    root=st.no_links(Path(root)).resolve()
    path=root/'CORE.json'
    meta=json.loads(path.read_text(encoding='utf-8'))
    files={}
    for candidate in root.rglob('*'):
        if '__pycache__' in candidate.parts or not candidate.is_file():
            continue
        rel=candidate.relative_to(root).as_posix()
        if rel=='CORE.json':
            continue
        if rel.startswith(('preferences/','legacy/','s1/','s2/','.wb-state/')):
            raise ValueError('Private/state path in core: '+rel)
        files[rel]=st.hash_file(candidate)
    meta['files']=dict(sorted(files.items()))
    if version:
        meta['version']=version
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    result=verify(root)
    result['resealed']=True
    result['note']='Manifest rewritten from the current files; run the test suite before syncing.'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','export','reseal','diff'));parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path);parser.add_argument('--review',type=Path)
    parser.add_argument('--reference',type=Path,
                        help='diff: same-version original directory, for classifying differences')
    parser.add_argument('--version',help='reseal: also set this core version (for example 0.22.4-beta.1)')
    parser.add_argument('--allow-host-files',action='store_true',
                        help='accept known host/OS bookkeeping files (for example _user_meta.json) in the core directory')
    args=parser.parse_args()
    if args.command=='export' and args.output is None:parser.error('--output required')
    try:
        if args.command=='verify':
            result=verify(args.root,allow_host_files=args.allow_host_files)
        elif args.command=='reseal':
            result=reseal(args.root,args.version)
        elif args.command=='diff':
            result=diff(args.root,args.reference)
        else:
            result=export(args.root,args.output,args.review)
        print(json.dumps(result))
    except (ValueError,OSError,KeyError) as exc:print('ERROR: '+str(exc),file=sys.stderr);raise SystemExit(1)
