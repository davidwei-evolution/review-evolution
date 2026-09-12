"""Installation-local consent, separate from transferable private experience."""
from pathlib import Path
import json
import safe_store as st

def policy(core):
    core=Path(core)
    path=core/'runtime-policy.json'
    if not path.exists():
        meta=json.loads((core/'CORE.json').read_text(encoding='utf-8'))
        if 'runtime-policy.json' in meta.get('files',{}):
            raise ValueError('Missing runtime policy; never fall back to development mode')
        # Compatibility with pre-0.22 cores and synthetic legacy fixtures.
        return {'schema':1,'edition':'development','s3_available':True}
    row=json.loads(path.read_text(encoding='utf-8'))
    if set(row)!={'schema','edition','s3_available'} or row['schema']!=1 or row['edition'] not in ('development','public') or type(row['s3_available']) is not bool:
        raise ValueError('Invalid runtime policy')
    meta=json.loads((core/'CORE.json').read_text(encoding='utf-8'))
    if st.hash_file(path)!=meta['files'].get('runtime-policy.json'):
        raise ValueError('Runtime policy integrity mismatch')
    return row

def choice_path(core):
    import experience as e
    key=st.digest(e.encoded({'core':str(Path(core).resolve()),'context':e.active_context()}))
    return e.data_home()/'optional-modules'/(key+'.json')

def status(core):
    row=policy(core)
    if row['edition']=='development':
        return dict(row,enabled=True,choice='local-development')
    path=st.no_links(choice_path(core))
    choice=None
    if path.exists():
        import experience as e
        saved=e.read(path)
        if not isinstance(saved,dict) or saved.get('schema')!=1 or type(saved.get('enabled')) is not bool:
            raise ValueError('Invalid S3 choice; preserve it and ask user to choose again')
        choice=saved['enabled']
    enabled=row['s3_available'] and choice is True
    result=dict(row,enabled=enabled,
                choice='not-selected' if choice is None else 'enabled' if choice else 'declined')
    if not enabled:
        # Without this line "enabled=false" next to leftover S3 data reads like a contradiction.
        result['note']=('S3 未启用：如档案中已有历史 S3 记录，原件只读保留、不会被删除，'
                        '但本状态与 query-s3 不读取它们；需要读取请使用官方含 S3 版并由你明确选择启用。')
    return result

def choose(core,enabled,confirmed=False):
    if not confirmed:raise ValueError('Explain S3 purpose/token cost and obtain user choice first (--confirmed)')
    row=policy(core)
    if row['edition']!='public':raise ValueError('Local development policy is not a public user option')
    if enabled and not row['s3_available']:raise ValueError('S3_NOT_INSTALLED: choose the official S3 package; existing data remains intact')
    path=st.no_links(choice_path(core));path.parent.mkdir(parents=True,exist_ok=True)
    with st.locked(path.parent):
        old=st.hash_file(path)
        st.apply(path.parent,{path.name:st.json_bytes({'schema':1,'enabled':bool(enabled)})},
                 {path.name:old},already_locked=True)
    return status(core)

def require(core):
    row=status(core)
    if row['edition']=='development':return
    if not row['s3_available']:raise ValueError('S3_NOT_INSTALLED: S1/S2 and complete backup remain available')
    if not row['enabled']:raise ValueError('S3_NOT_ENABLED: explain purpose/token cost and ask for explicit choice')
    # Import only after consent. Core compatibility readers do not load this module.
    import importlib
    importlib.import_module('s3_optional')
