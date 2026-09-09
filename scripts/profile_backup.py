"""Complete private file backup and restore to a new directory. No automatic binding."""
from pathlib import Path
import os,stat,tempfile
import experience as e
import safe_store as st
import core_package as cp

BACKUP_FILES=40000
BACKUP_TOTAL=256*1024*1024
BACKUP_FILE=64*1024*1024


def inventory(root, capture=False):
    root=st.no_links(root).resolve();rows={};payload={};total=0
    for path in sorted(root.rglob('*')):
        st.no_links(path)
        if path.is_dir():continue
        if not stat.S_ISREG(path.stat().st_mode):raise ValueError('Unsupported filesystem entry')
        rel=path.relative_to(root).as_posix()
        if rel==st.STATE+'/lock':continue
        st.relative(rel)
        size=path.stat().st_size;total+=size
        if size>BACKUP_FILE or total>BACKUP_TOTAL or len(rows)>=BACKUP_FILES:
            raise ValueError('Backup capacity exceeded; nothing is silently omitted')
        data=path.read_bytes()
        if len(data)!=size:raise ValueError('File changed during backup read')
        rows[rel]={'size':size,'sha256':st.digest(data)}
        if capture:payload[rel]=data
    return rows,payload


def directories(root):
    # Lock acquisition may create this otherwise empty directory after preview.
    result=[st.STATE]
    for path in root.rglob('*'):
        st.no_links(path)
        if path.is_dir() and path.relative_to(root).as_posix()!=st.STATE:result.append(path.relative_to(root).as_posix())
    if len(result)>BACKUP_FILES:raise ValueError('Too many directories')
    return sorted(result)

def checked_profile(root):
    e.info(root);e.query(root)
    e.query_s3(root);e.s1_metrics(root);e.s2_metrics(root)
    e.load_update_ledger(root);e.trusted_sources_view(root)


def backup_plan(root):
    root=e.profile_root(root);e.info(root)
    before,_=inventory(root);dirs=directories(root)
    checked_profile(root)
    after,_=inventory(root);e.info(root)
    if before!=after or dirs!=directories(root):raise ValueError('Profile changed during backup preview')
    plan={'format':1,'kind':'complete-profile-backup','profile_id':e.info(root)['profile_id'],
          'files':before,'directories':dirs,'excluded':[st.STATE+'/lock'],
          'reader_core':cp.verify(e.CORE)['sha256'],'reader_version':cp.verify(e.CORE)['version'],
          'root':str(root),'encrypted':False}
    plan['plan_id']=st.digest(st.json_bytes(plan));return plan


def separate_new_target(source,target):
    source=st.no_links(source).resolve();target=e.profile_root(target)
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('Use a separate output directory')
    if target.exists():raise ValueError('Output must not exist; never overwrite a profile')
    return target


def publish_directory(target, writer):
    if os.name!='nt':raise ValueError('Directory publication currently validated on Windows only')
    st.no_links(target.parent)
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.wb-candidate-',dir=target.parent))
    try:
        writer(stage)
        st.no_links(target)
        if target.exists():raise ValueError('Target appeared; original retained')
        # Windows rename refuses an existing destination; final target is a fresh directory.
        stage.rename(target)
    except BaseException:
        # Keep partial output for diagnosis; it is never reported as a completed backup/profile.
        raise


def backup(root,out,plan_id):
    root=e.profile_root(root);out=separate_new_target(root,out)
    # Acquiring the existing writer lock is part of this explicitly requested write operation.
    with st.locked(root):
        plan=backup_plan(root)
        if plan['plan_id']!=plan_id:raise ValueError('Stale backup plan; preview again')
        rows,payload=inventory(root,True)
        if rows!=plan['files'] or directories(root)!=plan['directories']:raise ValueError('Profile changed after preview')
        manifest={k:v for k,v in plan.items() if k not in ('root','plan_id')}
        manifest['backup_id']=st.digest(st.json_bytes(manifest))
        def write(stage):
            for rel in manifest['directories']:st.inside(stage,'data/'+rel).mkdir(parents=True,exist_ok=True)
            for rel,data in payload.items():st.atomic_bytes(st.inside(stage,'data/'+rel),data)
            if inventory(root)[0]!=rows or directories(root)!=manifest['directories']:raise ValueError('Profile changed during backup')
            st.atomic_bytes(stage/'backup.json',st.json_bytes(manifest))
            validate_backup(stage)
        publish_directory(out,write)
    return {'status':'BACKED_UP','backup_id':manifest['backup_id'],'files':len(rows),'encrypted':False}


def validate_backup(path):
    path=st.no_links(path).resolve()
    manifest=e.read(path/'backup.json')
    required={'format','kind','profile_id','files','excluded','reader_core','reader_version','encrypted','backup_id','directories'}
    if not isinstance(manifest,dict) or set(manifest)!=required or manifest['format']!=1 or manifest['kind']!='complete-profile-backup':
        raise ValueError('Unsupported backup format')
    if manifest['excluded']!=[st.STATE+'/lock'] or manifest['encrypted'] is not False:
        raise ValueError('Unsupported backup exclusions or encryption')
    unsigned={k:v for k,v in manifest.items() if k!='backup_id'}
    if st.digest(st.json_bytes(unsigned))!=manifest['backup_id']:raise ValueError('Backup manifest changed')
    if manifest['reader_core']!=cp.verify(e.CORE)['sha256']:
        raise ValueError('Different reader core; compatibility review required before restore')
    if {p.name for p in path.iterdir()}!={'data','backup.json'}:raise ValueError('Unexpected backup contents')
    if (path/'data'/st.STATE/'lock').exists():raise ValueError('Backup contains volatile lock')
    rows,payload=inventory(path/'data',True)
    if rows!=manifest['files'] or directories(path/'data')!=manifest['directories']:raise ValueError('Backup contents changed or incomplete')
    checked_profile(path/'data')
    if e.info(path/'data')['profile_id']!=manifest['profile_id']:raise ValueError('Backup identity mismatch')
    if inventory(path/'data')[0]!=rows or directories(path/'data')!=manifest['directories']:
        raise ValueError('Backup changed during validation')
    if e.read(path/'backup.json')!=manifest:raise ValueError('Backup manifest changed during validation')
    return manifest,payload


def restore_plan(path,target):
    target=separate_new_target(path,target)
    # A restored profile must not be created in either installed or source core.
    e.profile_root(target)
    manifest,_=validate_backup(path)
    plan={'kind':'restore-new-profile','backup_id':manifest['backup_id'],
          'target':str(target),'files':len(manifest['files']),'binding_changed':False}
    plan['plan_id']=st.digest(st.json_bytes(plan));return plan


def restore(path,target,plan_id):
    plan=restore_plan(path,target)
    if plan['plan_id']!=plan_id:raise ValueError('Stale restore plan')
    manifest,payload=validate_backup(path)
    if manifest['backup_id']!=plan['backup_id']:raise ValueError('Backup changed after preview')
    target=Path(plan['target'])
    def write(stage):
        for rel in manifest['directories']:st.inside(stage,rel).mkdir(parents=True,exist_ok=True)
        for rel,data in payload.items():st.atomic_bytes(st.inside(stage,rel),data)
        if inventory(stage)[0]!=manifest['files']:raise ValueError('Restored files differ')
        checked_profile(stage)
        if inventory(stage)[0]!=manifest['files'] or directories(stage)!=manifest['directories']:
            raise ValueError('Restored files changed during validation')
    publish_directory(target,write)
    return {'status':'RESTORED','backup_id':manifest['backup_id'],'binding_changed':False,
            'next_step':'先显式指定新档案运行 status、query、query-s3、s1-metrics 和 s2-metrics；确认后才切换绑定。'}
