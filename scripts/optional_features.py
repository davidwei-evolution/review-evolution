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
    # 2026-09-13：对外形态是单一技能目录，不再声明内部可选模块，因此公开策略行只保留
    # {schema, edition}；开发形态仍带 s3_available。两者都接受，且公开行不得再出现该键。
    if set(row) not in ({'schema','edition','s3_available'},{'schema','edition'}) or row.get('schema')!=1 or row.get('edition') not in ('development','public'):
        raise ValueError('Invalid runtime policy')
    if 's3_available' in row and type(row['s3_available']) is not bool:
        raise ValueError('Invalid runtime policy')
    if row['edition']=='public' and 's3_available' in row:
        raise ValueError('Invalid runtime policy: public editions do not declare the internal module')
    row.setdefault('s3_available',row['edition']=='development')
    meta=json.loads((core/'CORE.json').read_text(encoding='utf-8'))
    if st.hash_file(path)!=meta['files'].get('runtime-policy.json'):
        raise ValueError('Runtime policy integrity mismatch')
    return row

def installation_choice_path(core):
    import experience as e
    core=st.no_links(Path(core)).resolve()
    key=st.digest(e.encoded({'core':str(core),'context':e.active_context()}))
    return st.inside(core.parent,'.review-evolution-choices/'+key+'.json')

def choice_path(core):
    import experience as e
    installed=installation_choice_path(core)
    if installed.exists():return installed
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
    if not enabled and row['edition']=='development':
        # Without this line "enabled=false" next to leftover S3 data reads like a contradiction.
        result['note']=('S3 未启用：如档案中已有历史 S3 记录，原件只读保留、不会被删除，'
                        '但本状态与 query-s3 不读取它们；需要读取请使用官方统一安装包选择加装并启用S3。')
    return result

def choose(core,enabled,confirmed=False):
    if not confirmed:raise ValueError('Explain S3 purpose/token cost and obtain user choice first (--confirmed)')
    row=policy(core)
    if row['edition']!='public':raise ValueError('Local development policy is not a public user option')
    if enabled and not row['s3_available']:raise ValueError('S3_NOT_INSTALLED: use the official unified installer with --s3 yes; existing data remains intact')
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
