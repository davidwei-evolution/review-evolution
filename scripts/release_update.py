"""Explicit public release checks and content-bound, local-only core updates.

No background jobs, downloads, candidate-code execution or implicit installation.
"""
import argparse
from datetime import datetime,timezone
import functools
import http.client
import json
from pathlib import Path
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

import core_package as cp
import release_gate as gate
import safe_store as st

CORE=Path(__file__).resolve().parents[1]
REPO='davidwei-evolution/review-evolution'
PAGE='https://github.com/'+REPO+'/releases'
API='https://api.github.com/repos/'+REPO+'/releases'
MAX_RESPONSE=8*1024*1024
MAX_PAGES=3
VERSION=re.compile(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z')

def version(value):
    m=VERSION.fullmatch(value) if isinstance(value,str) and len(value)<200 else None
    if not m:raise ValueError('Unsupported version; review version series instead of guessing')
    pre=m[4].split('.') if m[4] else []
    if any(p.isdigit() and len(p)>1 and p[0]=='0' for p in pre):
        raise ValueError('Invalid numeric prerelease')
    return (tuple(int(m[i]) for i in (1,2,3)),pre)

def compare(a,b):
    ac,ap=version(a);bc,bp=version(b)
    if ac!=bc:return (ac>bc)-(ac<bc)
    if not ap or not bp:return (not ap)-(not bp)
    for x,y in zip(ap,bp):
        if x==y:continue
        if x.isdigit() and y.isdigit():return (int(x)>int(y))-(int(x)<int(y))
        if x.isdigit()!=y.isdigit():return -1 if x.isdigit() else 1
        return (x>y)-(x<y)
    return (len(ap)>len(bp))-(len(ap)<len(bp))

def parse_json(raw):
    if len(raw)>MAX_RESPONSE:raise ValueError('Response too large')
    def unique(pairs):
        obj={}
        for k,v in pairs:
            if k in obj:raise ValueError('Duplicate JSON field')
            obj[k]=v
        return obj
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Redirect refused; verify repository identity manually')

def fetch_page(page):
    req=urllib.request.Request(API+'?per_page=100&page='+str(page),headers={
        'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28',
        'User-Agent':'review-evolution-release-check'})
    opener=urllib.request.build_opener(NoRedirect())
    with opener.open(req,timeout=15) as response:
        if response.geturl()!=req.full_url:raise ValueError('Unexpected response origin')
        return parse_json(response.read(MAX_RESPONSE+1))

def fetch_releases():
    rows=[]
    for page in range(1,MAX_PAGES+1):
        part=fetch_page(page)
        if not isinstance(part,list) or len(part)>100:raise ValueError('Unexpected release list')
        rows.extend(part)
        if len(part)<100:return rows,True
    return rows,False

def release_url(value):
    if not isinstance(value,str):return False
    u=urllib.parse.urlsplit(value)
    return u.scheme=='https' and u.netloc=='github.com' and u.path.startswith('/'+REPO+'/releases/') and not u.query and not u.fragment

def evaluate(local,rows,complete=True,include_prerelease=False):
    local_v=local['version'];version(local_v)
    base={'local_version':local_v,'repository':REPO,'releases_page':PAGE,
          'checked_at':datetime.now(timezone.utc).isoformat(),'changes':[],
          'downloaded':False,'installed':False,'update_available':False,
          'compatibility':'not-checked','release_notes_are_untrusted':True}
    if local.get('release_series')!='modular-1':
        return {**base,'status':'SERIES_REVIEW_REQUIRED','message':'本机版本体系需人工核对，未建议升级。'}
    if not isinstance(rows,list):raise ValueError('Expected release list')
    if not complete:
        return {**base,'status':'INCOMPLETE','message':'发布列表未读取完整，不能判断是否有更新。'}
    eligible=[];unknown=[];seen=set()
    for r in rows:
        if not isinstance(r,dict) or type(r.get('draft')) is not bool or type(r.get('prerelease')) is not bool:
            raise ValueError('Unexpected release fields')
        if r['draft']:continue
        if r['prerelease'] and not include_prerelease:continue
        try:rv=version(r.get('tag_name'))
        except ValueError:
            unknown.append(r.get('tag_name'));continue
        if rv[1] and not include_prerelease:continue
        if not release_url(r.get('html_url')) or not isinstance(r.get('published_at'),str):
            raise ValueError('Invalid release origin/date')
        stamp=datetime.fromisoformat(r['published_at'].replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('Release date requires timezone')
        if not isinstance(r.get('body'),(str,type(None))):raise ValueError('Invalid release notes')
        identity=(rv[0],tuple(rv[1]))
        if identity in seen:raise ValueError('Ambiguous duplicate version precedence')
        seen.add(identity);eligible.append(r)
    if unknown:
        return {**base,'status':'VERSION_REVIEW_REQUIRED','unknown_versions':unknown,
                'message':'存在无法可靠比较的发布标签，需要核对，未宣称无更新。'}
    if not eligible:
        return {**base,'status':'NO_RELEASE' if not rows else 'NO_ELIGIBLE_RELEASE',
                'message':'仓库暂无可比较的正式发布；这不代表没有代码变化。'}
    eligible.sort(key=functools.cmp_to_key(lambda a,b:compare(a['tag_name'],b['tag_name'])))
    latest=eligible[-1];v=latest['tag_name']
    base.update(latest_version=v,release_url=latest['html_url'])
    if version(v)[0][0]>=2 and version(local_v)[0][0]<1:
        return {**base,'status':'SERIES_REVIEW_REQUIRED','message':'远端与本机可能属于不同历史版本体系，先核对，不能按数字直接升级。'}
    diff=compare(v,local_v)
    if diff<=0:
        return {**base,'status':'UP_TO_DATE' if diff==0 else 'LOCAL_AHEAD',
                'message':'本机与最新发布版本相同。' if diff==0 else '本机版本高于当前发布，不降级。'}
    changes=[]
    for r in eligible:
        if compare(r['tag_name'],local_v)>0:
            body=r.get('body') or ''
            changes.append({'version':r['tag_name'],'url':r['html_url'],
                'notes':body[:20000],'notes_missing':not body.strip(),'notes_truncated':len(body)>20000})
    return {**base,'status':'UPDATE_AVAILABLE','update_available':True,'changes':changes,
            'message':'发现新版 '+v+'（本机 '+local_v+'）。请先阅读变化与兼容性说明。',
            'question':'是否需要更新？确认后我会获取指定版本、核验并备份，再替换核心，保留你的经验。'}

def check(core=CORE,online=False,snapshot=None,include_prerelease=False):
    try:
        cp.verify(core)
        local=parse_json((Path(core)/'CORE.json').read_bytes())
        if online and snapshot is not None:raise ValueError('Select online or a saved snapshot, not both')
        if online:
            rows,complete=fetch_releases();source='github-api-live'
        elif snapshot is not None:
            # Raw saved API lists are accepted only if the final page is short.
            rows=parse_json(st.no_links(snapshot).read_bytes());complete=isinstance(rows,list) and len(rows)<100
            source='offline-snapshot-not-live'
        else:
            return {'status':'NOT_CHECKED','message':'尚未联网检查。用户要求检查后，可显式运行 check --online。'}
        return {**evaluate(local,rows,complete,include_prerelease),'source':source}
    except urllib.error.HTTPError as ex:
        status='RATE_LIMITED' if ex.code in (403,429) else 'NOT_FOUND' if ex.code==404 else 'HTTP_ERROR'
        ex.close()
        return {'status':status,'http_status':ex.code,'message':'本次无法检查发布，请稍后重试；未判断为无更新。'}
    except (ssl.SSLError,) as ex:
        return {'status':'TLS_ERROR','message':'安全连接验证失败，已停止；不关闭证书验证。'}
    except (TimeoutError,socket.timeout):
        return {'status':'TIMEOUT','message':'检查超时，未判断为无更新。'}
    except urllib.error.URLError as ex:
        status='TLS_ERROR' if isinstance(ex.reason,ssl.SSLError) else 'TIMEOUT' if isinstance(ex.reason,(TimeoutError,socket.timeout)) else 'NETWORK_ERROR'
        return {'status':status,'message':'无法连接发布服务；未判断为无更新。'}
    except http.client.HTTPException:
        return {'status':'NETWORK_ERROR','message':'发布响应中断或损坏；未判断为无更新。'}
    except (ValueError,KeyError,TypeError,OSError) as ex:
        return {'status':'VALIDATION_ERROR','message':'本机或发布信息未通过校验；停止自动判断。','detail':str(ex)}

def core_bytes(root):
    root=st.no_links(root).resolve()
    count=total=0
    for path in root.rglob('*'):
        st.no_links(path)
        if path.is_file():
            count+=1;total+=path.stat().st_size
            if count>200 or path.stat().st_size>4*1024*1024 or total>32*1024*1024:
                raise ValueError('Core exceeds automatic update capacity')
    cp.verify(root)
    meta=parse_json((root/'CORE.json').read_bytes())
    if meta.get('core_api')!=1:raise ValueError('Unsupported core API; manual migration required')
    if len(meta['files'])>200:raise ValueError('Core too large for automatic update')
    payload={}
    for rel in [*meta['files'],'CORE.json']:
        if not gate.permitted(rel):raise ValueError('New core component needs review: '+rel)
        path=st.inside(root,rel)
        if path.stat().st_size>4*1024*1024:raise ValueError('Core file too large')
        payload[rel]=path.read_bytes()
        if rel!='CORE.json' and st.digest(payload[rel])!=meta['files'][rel]:raise ValueError('Source changed')
    if sum(map(len,payload.values()))>32*1024*1024:raise ValueError('Core exceeds update budget')
    if parse_json(payload['CORE.json'])!=meta:raise ValueError('Manifest changed')
    return meta,payload

def install_plan(candidate,target,allow_dev=False,expected_version=None):
    candidate=st.no_links(candidate).resolve();target=st.no_links(target).resolve()
    if candidate.is_relative_to(target) or target.is_relative_to(candidate):raise ValueError('Use a separate candidate directory')
    old,old_bytes=core_bytes(target);new,new_bytes=core_bytes(candidate)
    version(expected_version)
    if new['version'].removeprefix('v')!=expected_version.removeprefix('v'):
        raise ValueError('Candidate version does not match the reviewed release tag')
    for field in ('canonical_name','lineage_id','release_series','data_schema','core_api'):
        if new.get(field)!=old.get(field):raise ValueError('Identity/schema changed: manual migration required')
    if compare(new['version'],old['version'])<=0:raise ValueError('Update must be strictly newer; never downgrade')
    if new.get('release_ready') is not True and not allow_dev:raise ValueError('Development release requires explicit allow-dev review')
    if set(old_bytes)-set(new_bytes):raise ValueError('Update removes files; explicit migration/deletion review required')
    changes={rel:{'before':st.digest(old_bytes[rel]) if rel in old_bytes else None,'after':st.digest(data)}
             for rel,data in new_bytes.items() if old_bytes.get(rel)!=data}
    plan={'schema':1,'candidate':str(candidate),'target':str(target),'allow_dev':allow_dev,'expected_version':expected_version,
          'from_version':old['version'],'to_version':new['version'],'changes':changes,
          'candidate_manifest':st.digest(new_bytes['CORE.json']),'target_manifest':st.digest(old_bytes['CORE.json']),
          'note':'Local content integrity only; verify official asset provenance and obtain user approval before applying.'}
    plan['plan_id']=st.digest(st.json_bytes(plan));return plan

def install(candidate,target,plan_id,allow_dev=False,expected_version=None):
    target=st.no_links(target).resolve()
    with st.locked(target.parent):
        plan=install_plan(candidate,target,allow_dev,expected_version)
        if plan['plan_id']!=plan_id:raise ValueError('Stale/unapproved update plan')
        meta,payload=core_bytes(candidate)
        if st.digest(payload['CORE.json'])!=plan['candidate_manifest']:raise ValueError('Candidate changed after preflight')
        writes={target.name+'/'+rel:payload[rel] for rel in plan['changes']}
        expected={target.name+'/'+rel:spec['before'] for rel,spec in plan['changes'].items()}
        for rel,spec in plan['changes'].items():
            if st.digest(payload[rel])!=spec['after']:raise ValueError('Candidate content changed')
        tx=st.apply(target.parent,writes,expected,already_locked=True)
        result=cp.verify(target)
        if result['sha256']!=plan['candidate_manifest']:raise ValueError('Installed verification failed; retain backup for recovery')
        return {'status':'UPDATED','version':result['version'],'transaction':tx,
                'backup':str(target.parent/st.STATE/'transactions'/tx),
                'message':'核心文件更新并核验完成。请新开相关会话确认技能可用，再查询已有经验。'}

def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('check');q.add_argument('--core',type=Path,default=CORE)
    mode=q.add_mutually_exclusive_group();mode.add_argument('--online',action='store_true');mode.add_argument('--snapshot',type=Path)
    q.add_argument('--include-prerelease',action='store_true')
    for name in ('plan-install','install'):
        q=sub.add_parser(name);q.add_argument('candidate',type=Path);q.add_argument('--target',type=Path,default=CORE)
        q.add_argument('--expected-version',required=True)
        q.add_argument('--allow-dev',action='store_true')
        if name=='install':q.add_argument('--plan-id',required=True)
    a=p.parse_args()
    if a.command=='check':result=check(a.core,a.online,a.snapshot,a.include_prerelease)
    elif a.command=='plan-install':result=install_plan(a.candidate,a.target,a.allow_dev,a.expected_version)
    else:result=install(a.candidate,a.target,a.plan_id,a.allow_dev,a.expected_version)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status') in ('VALIDATION_ERROR','RATE_LIMITED','NETWORK_ERROR','TIMEOUT','TLS_ERROR','HTTP_ERROR','NOT_FOUND','INCOMPLETE'):
        return 1
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as ex:
        print('UPDATE_STOPPED: '+str(ex),file=sys.stderr);raise SystemExit(1)
