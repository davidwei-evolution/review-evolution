"""Explicit public release checks, bounded downloads and content-bound, local-only core updates.

No background jobs, automatic downloads, candidate-code execution or implicit installation.
"""
import argparse
import base64
from datetime import datetime,timezone
import functools
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
import tempfile
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
CONTENTS='https://api.github.com/repos/'+REPO+'/contents/CORE.json'
DOWNLOAD_PREFIX='/'+REPO+'/releases/download/'
MAX_RESPONSE=8*1024*1024
MAX_PAGES=3
MAX_ASSETS=50
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

class AllowedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urllib.parse.urlsplit(newurl)
        host=(u.netloc or '').lower()
        if u.scheme!='https' or not (host=='github.com' or host=='githubusercontent.com' or host.endswith('.githubusercontent.com')):
            raise ValueError('Redirect to untrusted host refused: '+u.netloc)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

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

def api_get(url):
    req=urllib.request.Request(url,headers={
        'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28',
        'User-Agent':'review-evolution-release-check'})
    opener=urllib.request.build_opener(NoRedirect())
    with opener.open(req,timeout=15) as response:
        if response.geturl()!=url:raise ValueError('Unexpected response origin')
        return response.read(MAX_RESPONSE+1)

def release_url(value):
    if not isinstance(value,str):return False
    u=urllib.parse.urlsplit(value)
    return u.scheme=='https' and u.netloc=='github.com' and u.path.startswith('/'+REPO+'/releases/') and not u.query and not u.fragment

def asset_url(value):
    if not isinstance(value,str) or len(value)>2000:return False
    u=urllib.parse.urlsplit(value)
    return (u.scheme=='https' and u.netloc=='github.com'
            and u.path.startswith(DOWNLOAD_PREFIX) and len(u.path)>len(DOWNLOAD_PREFIX)
            and not u.query and not u.fragment)

def assets_of(row):
    assets=row.get('assets')
    if assets is None:return []
    if not isinstance(assets,list) or len(assets)>MAX_ASSETS:raise ValueError('Unexpected asset list')
    out=[]
    for a in assets:
        if not isinstance(a,dict):raise ValueError('Unexpected asset entry')
        name=a.get('name');url=a.get('browser_download_url');size=a.get('size')
        if not isinstance(name,str) or not name.strip() or len(name)>300:raise ValueError('Invalid asset name')
        if not asset_url(url):raise ValueError('Invalid asset URL')
        if not isinstance(size,int) or not 0<=size<=4*1024*1024*1024:raise ValueError('Invalid asset size')
        out.append({'name':name,'url':url,'size':size})
    return out

def failure(status,message,cross_check=True,**kw):
    row={'status':status,'message':message,'cross_check':cross_check}
    if cross_check:
        row['releases_page']=PAGE
    row.update(kw);return row

def evaluate(local,rows,complete=True,channel='all'):
    if channel not in ('all','stable'):raise ValueError('Unsupported channel')
    local_v=local['version'];version(local_v)
    base={'local_version':local_v,'repository':REPO,'releases_page':PAGE,
          'checked_at':datetime.now(timezone.utc).isoformat(),'changes':[],
          'downloaded':False,'installed':False,'update_available':False,
          'compatibility':'not-checked','release_notes_are_untrusted':True,'channel':channel}
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
        assets_of(r)
        if r['prerelease'] and channel=='stable':continue
        try:rv=version(r.get('tag_name'))
        except ValueError:
            unknown.append(r.get('tag_name'));continue
        if rv[1] and channel=='stable':continue
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
        message=('仓库没有任何可比较的发布；这不代表没有代码变化。'
                 if not rows else
                 '仓库暂无正式（非预发布）发布；可改用默认渠道查看试用版。'
                 if channel=='stable' else
                 '仓库没有可比较的发布（草稿/异常标签已排除）；不要据此断言无更新，先打开发布页交叉复核。')
        return {**base,'status':'NO_RELEASE' if not rows else 'NO_ELIGIBLE_RELEASE','message':message}
    eligible.sort(key=functools.cmp_to_key(lambda a,b:compare(a['tag_name'],b['tag_name'])))
    latest=eligible[-1];v=latest['tag_name']
    latest_type='prerelease' if latest['prerelease'] else 'release'
    base.update(latest_version=v,release_url=latest['html_url'],latest_release_type=latest_type)
    if version(v)[0][0]>=2 and version(local_v)[0][0]<1:
        return {**base,'status':'SERIES_REVIEW_REQUIRED','message':'远端与本机可能属于不同历史版本体系，先核对，不能按数字直接升级。'}
    diff=compare(v,local_v)
    if diff<=0:
        msg=('本机与最新发布版本相同（'+v+'，'+latest_type+'）。'
             if diff==0 else '本机版本高于当前发布，不降级。')
        return {**base,'status':'UP_TO_DATE' if diff==0 else 'LOCAL_AHEAD',
                'message':msg}
    changes=[]
    for r in eligible:
        if compare(r['tag_name'],local_v)>0:
            body=r.get('body') or ''
            changes.append({'version':r['tag_name'],'url':r['html_url'],
                'notes':body[:20000],'notes_missing':not body.strip(),'notes_truncated':len(body)>20000,
                'release_type':'prerelease' if r['prerelease'] else 'release','assets':assets_of(r)})
    return {**base,'status':'UPDATE_AVAILABLE','update_available':True,'changes':changes,
            'message':'发现新版 '+v+'（'+latest_type+'，本机 '+local_v+'）。请先阅读变化与兼容性说明。',
            'question':'是否需要更新？确认后我会获取指定版本、核验并备份，再替换核心，保留你的经验。'}

def _edition_of(payload):
    """U10: expose the edition and optional-module availability of a core payload."""
    try:
        row=parse_json(payload.get('runtime-policy.json',b'{}'))
    except (ValueError,TypeError):
        return {'edition':None,'s3_available':None}
    return {'edition':row.get('edition'),'s3_available':bool(row.get('s3_available'))}


def check(core=CORE,online=False,snapshot=None,channel='all'):
    try:
        try:
            cp.verify(core)
        except (ValueError,OSError,KeyError,TypeError) as ex:
            # U7: a broken local install is not a publishing problem. Saying "需要联网复核"
            # here sent a real run off chasing the network instead of the local file.
            return failure('LOCAL_CORE_INVALID',
                           '本机已安装的核心未通过完整性校验；这是本机问题，与发布源无关，不要反复联网重试。',
                           cross_check=False,
                           cross_check_reason='本机完整性问题，联网复核无关。',
                           detail=str(ex),
                           next_step=('先运行 python -B scripts/core_package.py verify --root <技能目录>；'
                                      '再用 python -B scripts/core_package.py diff --root <技能目录> '
                                      '[--reference <同版本原包>] 做只读诊断。'+cp.HOST_REWRITE_HINT))
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
        result={**evaluate(local,rows,complete,channel),'source':source}
        if result['status']!='UPDATE_AVAILABLE':
            result['cross_check']={'releases_page':PAGE,
                                   'reason':'脚本的否定/错误结果必须先经发布页独立复核，不能直接对用户断言“没有新版”。'}
        return result
    except urllib.error.HTTPError as ex:
        status='RATE_LIMITED' if ex.code in (403,429) else 'NOT_FOUND' if ex.code==404 else 'HTTP_ERROR'
        ex.close()
        return failure(status,'本次无法检查发布，请稍后重试；未判断为无更新。',http_status=ex.code)
    except (ssl.SSLError,) as ex:
        return failure('TLS_ERROR','安全连接验证失败，已停止；不关闭证书验证。')
    except (TimeoutError,socket.timeout):
        return failure('TIMEOUT','检查超时，未判断为无更新。')
    except urllib.error.URLError as ex:
        status='TLS_ERROR' if isinstance(ex.reason,ssl.SSLError) else 'TIMEOUT' if isinstance(ex.reason,(TimeoutError,socket.timeout)) else 'NETWORK_ERROR'
        return failure(status,'无法连接发布服务；未判断为无更新。')
    except http.client.HTTPException:
        return failure('NETWORK_ERROR','发布响应中断或损坏；未判断为无更新。')
    except (ValueError,KeyError,TypeError,OSError) as ex:
        return failure('VALIDATION_ERROR','本机或发布信息未通过校验；停止自动判断。',detail=str(ex))

def fetch_manifest_at_tag(tag):
    version(tag)
    url=CONTENTS+'?ref='+urllib.parse.quote(tag,safe='')
    data=api_get(url)
    row=parse_json(data)
    if row.get('encoding')!='base64' or not isinstance(row.get('content'),str):
        raise ValueError('Unexpected remote manifest encoding')
    try:raw=base64.b64decode(''.join(row['content'].split()),validate=True)
    except (ValueError,TypeError) as ex:raise ValueError('Remote manifest is not valid base64') from ex
    return raw

def remote_tag_check(tag,core=CORE):
    try:
        cp.verify(core)
        local=parse_json((Path(core)/'CORE.json').read_bytes())
        remote=parse_json(fetch_manifest_at_tag(tag))
    except urllib.error.HTTPError as ex:
        status='RATE_LIMITED' if ex.code in (403,429) else 'NOT_FOUND' if ex.code==404 else 'HTTP_ERROR'
        ex.close()
        return failure(status,'本次无法读取远端 tag 清单，请稍后重试。',http_status=ex.code)
    except (ssl.SSLError,):
        return failure('TLS_ERROR','安全连接验证失败，已停止；不关闭证书验证。')
    except (TimeoutError,socket.timeout):
        return failure('TIMEOUT','读取远端 tag 清单超时。')
    except urllib.error.URLError as ex:
        status='TLS_ERROR' if isinstance(ex.reason,ssl.SSLError) else 'TIMEOUT' if isinstance(ex.reason,(TimeoutError,socket.timeout)) else 'NETWORK_ERROR'
        return failure(status,'无法连接发布服务。')
    except http.client.HTTPException:
        return failure('NETWORK_ERROR','发布响应中断或损坏。')
    except (ValueError,KeyError,TypeError,OSError) as ex:
        return failure('VALIDATION_ERROR','远端或本机清单未通过校验；停止自动判断。',detail=str(ex))
    same=local==remote
    return {'status':'TAG_MATCH' if same else 'TAG_MISMATCH','tag':tag,
            'local_version':local.get('version'),'remote_version':remote.get('version'),
            'match':same,
            'message':('远端 tag 内容与本地候选一致，可以基于该 tag 确认/发布。'
                       if same else
                       '远端 tag 内容与本地候选不一致；不要基于该 tag 发布，先在内容一致的提交上重建 tag 或推送一致提交。'),
            'releases_page':PAGE,'checked_at':datetime.now(timezone.utc).isoformat()}

def download_asset(url,out,sha256=None,max_bytes=64*1024*1024,force=False):
    if not asset_url(url):raise ValueError('Unsupported asset URL; only https://github.com/'+REPO+'/releases/download/ links are accepted')
    out=st.no_links(Path(out)).resolve()
    if not out.parent.is_dir():raise ValueError('Output directory does not exist: '+str(out.parent))
    if out.exists() and not force:raise ValueError('Output already exists; choose another path or pass --force')
    if max_bytes<1 or max_bytes>512*1024*1024:raise ValueError('max-bytes out of range')
    req=urllib.request.Request(url,headers={'User-Agent':'review-evolution-release-check'})
    opener=urllib.request.build_opener(AllowedRedirect())
    fd,tmp=tempfile.mkstemp(prefix='.download-',suffix='.part',dir=str(out.parent))
    os.close(fd)
    try:
        with open(tmp,'wb') as fh, opener.open(req,timeout=30) as response:
            total=0
            while True:
                chunk=response.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>max_bytes:raise ValueError('Asset exceeds '+str(max_bytes)+' bytes; refused')
                fh.write(chunk)
        digest=st.hash_file(Path(tmp))
        if sha256 is not None:
            if not isinstance(sha256,str) or len(sha256)!=64 or sha256.lower()!=digest.lower():
                raise ValueError('SHA-256 mismatch: expected '+str(sha256)+', got '+digest)
        os.replace(tmp,str(out))
    except BaseException:
        try:os.unlink(tmp)
        except OSError:pass
        raise
    return {'status':'DOWNLOADED','path':str(out),'bytes':total,'sha256':digest,
            'expected_sha256':sha256,'message':'下载完成。仅字节完整不代表作者身份或代码安全，下一步仍需解压预检与内容核验。'}

def checked_core(root,label,reviewed=None,tolerate=()):
    if (Path(root)/'BUNDLE.json').is_file():
        raise ValueError('这是已停止支持的旧版统一安装包形态：请改为把技能目录直接交给目标位置，或用本更新器的 plan-install/install 处理；不要把这个外层目录当作已安装核心。私人档案不受影响。')
    try:return core_bytes(root,reviewed,tolerate=tolerate)
    except ValueError as ex:
        message=label+' core invalid at '+str(root)+': '+str(ex)
        # N1 (2026-09-12): verify() already appends the guidance, so only add it when absent -
        # otherwise the same paragraph lands twice and reads like two different suggestions.
        if (cp.HOST_REWRITE_HINT not in message
                and any(token in str(ex) for token in
                        ('Core content mismatch','Core is incomplete','unexpected files','Source changed'))):
            message+=' | '+cp.HOST_REWRITE_HINT
        raise ValueError(message) from ex


def rewrite_mismatches(root):
    """只读：列出安装目录里**与自身 CORE.json 清单不符**的文件（宿主改写/U1 场景）。不写盘。"""
    root=st.no_links(Path(root)).resolve()
    meta=parse_json((root/'CORE.json').read_bytes())
    files=meta.get('files')
    if not isinstance(files,dict):
        raise ValueError('Target core invalid at '+str(root)+': manifest inventory missing')
    missing=sorted(rel for rel in files if not st.inside(root,rel).is_file())
    if missing:
        raise ValueError('Target core invalid at '+str(root)+': Core is incomplete; missing files: '+repr(missing))
    return sorted(rel for rel,digest in files.items() if st.hash_file(st.inside(root,rel))!=digest)

def core_bytes(root,reviewed=None,tolerate=()):
    root=st.no_links(root).resolve()
    reviewed=set(reviewed or ())
    tolerate=set(tolerate or ())
    count=total=0
    for path in root.rglob('*'):
        st.no_links(path)
        if path.is_file():
            count+=1;total+=path.stat().st_size
            if count>200 or path.stat().st_size>4*1024*1024 or total>32*1024*1024:
                raise ValueError('Core exceeds automatic update capacity')
    cp.verify(root,tolerate=tolerate)
    meta=parse_json((root/'CORE.json').read_bytes())
    if meta.get('core_api')!=1:raise ValueError('Unsupported core API; manual migration required')
    if len(meta['files'])>200:raise ValueError('Core too large for automatic update')
    payload={};pending=[]
    for rel in [*meta['files'],'CORE.json']:
        if rel.startswith(('preferences/','legacy/','s1/','s2/','.wb-state/')):
            raise ValueError('Private/state path in core: '+rel)
        if not gate.permitted(rel) and rel not in reviewed:
            pending.append(rel);continue
        path=st.inside(root,rel)
        if path.stat().st_size>4*1024*1024:raise ValueError('Core file too large')
        payload[rel]=path.read_bytes()
        if rel!='CORE.json' and st.digest(payload[rel])!=meta['files'][rel] and rel not in tolerate:
            raise ValueError('Source changed')
    if pending:
        raise ValueError('New core component(s) need explicit review before update: '
                         +', '.join(sorted(pending))
                         +'. 完成迁移审查后用 --reviewed-manifest <JSON> 提供逐文件哈希与依据。')
    if sum(map(len,payload.values()))>32*1024*1024:raise ValueError('Core exceeds update budget')
    if parse_json(payload['CORE.json'])!=meta:raise ValueError('Manifest changed')
    return meta,payload

def parse_component_review(path,version,added,new_bytes):
    raw=st.no_links(Path(path)).read_bytes()
    rec=parse_json(raw)
    if rec.get('schema')!=1 or rec.get('purpose')!='component-review':
        raise ValueError('Review receipt must be schema 1 with purpose=component-review')
    if str(rec.get('version','')).removeprefix('v')!=str(version).removeprefix('v'):
        raise ValueError('Review receipt version does not match the candidate release')
    for key in ('reviewed_by','reason'):
        if not isinstance(rec.get(key),str) or not rec[key].strip():
            raise ValueError('Review receipt needs a non-empty '+key)
    files=rec.get('files')
    if not isinstance(files,dict) or len(files)>200:raise ValueError('Review receipt files must be a small dict')
    if set(files)!=set(added):
        raise ValueError('Review receipt must cover exactly the added files; missing='+str(sorted(set(added)-set(files)))
                         +' extra='+str(sorted(set(files)-set(added))))
    for rel in added:
        h=files.get(rel)
        if not isinstance(h,str) or len(h)!=64 or h.lower()!=st.digest(new_bytes[rel]):
            raise ValueError('Review receipt hash mismatch for '+rel)
    return {'receipt':st.digest(raw),'files':sorted(added),'reviewed_by':rec['reviewed_by'],'reason':rec['reason']}

def install_plan(candidate,target,allow_dev=False,expected_version=None,review_receipt=None,
                 repair_host_rewrite=False):
    candidate=st.no_links(candidate).resolve();target=st.no_links(target).resolve()
    if candidate.is_relative_to(target) or target.is_relative_to(candidate):raise ValueError('Use a separate candidate directory')
    # R1 (2026-09-13, W1)：目标核心被宿主「上传/注册」路径改写时，默认仍然拒绝并给出处置指引；
    # 只有显式 --repair-host-rewrite 才允许继续——且必须满足“每个不符文件都由候选包同名文件覆盖”，
    # 修复后的最终状态必须是候选包逐字节的官方内容（install 结束仍会整目录 verify）。
    repair=None
    if repair_host_rewrite:
        mismatched=rewrite_mismatches(target)
        if mismatched:
            repair={'requested':True,'files':mismatched}
        old,old_bytes=checked_core(target,'Target',tolerate=set(mismatched))
    else:
        old,old_bytes=checked_core(target,'Target')
    try:cmeta=parse_json((candidate/'CORE.json').read_bytes())
    except (ValueError,OSError) as ex:
        raise ValueError('Candidate core invalid at '+str(candidate)+': '+str(ex)) from ex
    if not isinstance(cmeta.get('files'),dict):
        raise ValueError('Candidate core invalid at '+str(candidate)+': manifest inventory missing')
    old_keys=set(parse_json(old_bytes['CORE.json'])['files'])
    added=sorted(set(cmeta['files'])-old_keys)
    if added and review_receipt is None:
        raise ValueError('Candidate adds new core component(s) without a review receipt: '
                         +', '.join(added)
                         +'. 完成迁移审查后重跑 plan-install --reviewed-manifest <JSON>。')
    review_path=st.no_links(Path(review_receipt)).resolve() if (added and review_receipt is not None) else None
    new,new_bytes=checked_core(candidate,'Candidate',reviewed=set(added) if added else None)
    before_edition=_edition_of(old_bytes);after_edition=_edition_of(new_bytes)
    capability_change=None
    if before_edition.get('s3_available') and not after_edition.get('s3_available'):
        # U10: switching from a development package to the public one silently drops an optional
        # capability. Say it out loud, without naming the internal module (user-visible message).
        capability_change={'s3_available':{'before':True,'after':False},
                           'note':('本候选的发行形态与当前安装不同（edition=public）：部分可选能力将不可用；'
                                   '既有记录只读保留、不会被删除，需要继续使用请换回原发行形态。')}
    version(expected_version)
    if new['version'].removeprefix('v')!=expected_version.removeprefix('v'):
        raise ValueError('Candidate version does not match the reviewed release tag')
    allowed_identities={(a,b) for a,b,_ in gate.ALLOWED_IDENTITIES}
    identity_change=None
    if new.get('canonical_name')!=old.get('canonical_name'):
        if (old.get('lineage_id')!=new.get('lineage_id')
                or (old.get('canonical_name'),old.get('lineage_id')) not in allowed_identities
                or (new.get('canonical_name'),new.get('lineage_id')) not in allowed_identities):
            raise ValueError('canonical_name change is not covered by the release gate identity table; manual migration required')
        identity_change={'from_canonical_name':old['canonical_name'],'to_canonical_name':new['canonical_name'],
                         'lineage_id':old['lineage_id']}
    for field in ('lineage_id','release_series','data_schema','core_api'):
        if new.get(field)!=old.get(field):raise ValueError('Identity/schema changed: manual migration required')
    if compare(new['version'],old['version'])<=0:raise ValueError('Update must be strictly newer; never downgrade')
    if new.get('release_ready') is not True and not allow_dev:raise ValueError('Development release requires explicit allow-dev review')
    if set(old_bytes)-set(new_bytes):raise ValueError('Update removes files; explicit migration/deletion review required')
    changes={rel:{'before':st.digest(old_bytes[rel]) if rel in old_bytes else None,'after':st.digest(data)}
             for rel,data in new_bytes.items() if old_bytes.get(rel)!=data}
    if repair:
        # 被改写的文件必须被候选包的官方同名文件覆盖；否则不提供“修复后继续”，避免留下半修状态。
        absent=sorted(rel for rel in repair['files'] if rel not in new_bytes)
        if absent:
            raise ValueError('Host-rewrite repair needs the same-named file inside the candidate package; missing: '
                             +repr(absent)+'. 请改用同版本原包复原该文件后再升级（见 references/install.md）。')
        for rel in repair['files']:
            changes[rel]={'before':st.digest(old_bytes[rel]),'after':st.digest(new_bytes[rel]),
                          'host_rewrite_repair':True}
        repair={'requested':True,
                'files':{rel:{'installed':st.digest(old_bytes[rel]),'manifest_expected':old['files'][rel]}
                         for rel in repair['files']}}
    component_review=parse_component_review(review_path,new['version'],added,new_bytes) if added else None
    plan={'schema':1,'candidate':str(candidate),'target':str(target),'allow_dev':allow_dev,'expected_version':expected_version,
          'from_version':old['version'],'to_version':new['version'],'changes':changes,
          'candidate_manifest':st.digest(new_bytes['CORE.json']),'target_manifest':st.digest(old_bytes['CORE.json']),
          'component_review':component_review,'identity_change':identity_change,
          'edition':after_edition.get('edition'),'s3_available':after_edition.get('s3_available'),
           'capability_change':capability_change,
           'repair':repair,
          'note':'Local content integrity only; verify official asset provenance and obtain user approval before applying.'}
    plan['plan_id']=st.digest(st.json_bytes(plan));return plan

def install(candidate,target,plan_id,allow_dev=False,expected_version=None,review_receipt=None,
            repair_host_rewrite=False):
    target=st.no_links(target).resolve()
    with st.locked(target.parent):
        plan=install_plan(candidate,target,allow_dev,expected_version,review_receipt,
                          repair_host_rewrite=repair_host_rewrite)
        if plan['plan_id']!=plan_id:raise ValueError('Stale/unapproved update plan')
        reviewed=set((plan.get('component_review') or {}).get('files') or [])
        meta,payload=checked_core(candidate,'Candidate',reviewed=reviewed)
        if st.digest(payload['CORE.json'])!=plan['candidate_manifest']:raise ValueError('Candidate changed after preflight')
        writes={target.name+'/'+rel:payload[rel] for rel in plan['changes']}
        expected={target.name+'/'+rel:spec['before'] for rel,spec in plan['changes'].items()}
        for rel,spec in plan['changes'].items():
            if st.digest(payload[rel])!=spec['after']:raise ValueError('Candidate content changed')
        tx=st.apply(target.parent,writes,expected,already_locked=True)
        result=cp.verify(target)
        if result['sha256']!=plan['candidate_manifest']:raise ValueError('Installed verification failed; retain backup for recovery')
        message='核心文件更新并核验完成。请新开相关会话确认技能可用，再查询已有经验。'
        if plan.get('repair'):
            message=('检测到已装核心中有 '+str(len(plan['repair']['files']))
                     +' 个文件与发布清单不符（宿主写入所致），已用候选包中的同名官方文件覆盖并重新校验；'
                     '核心现与发布清单逐字节一致。请新开相关会话确认技能可用，再查询已有经验。')
        if plan.get('capability_change'):
            message+=' 注意：'+plan['capability_change']['note']
        return {'status':'UPDATED','version':result['version'],'transaction':tx,
                'backup':str(target.parent/st.STATE/'transactions'/tx),
                'edition':plan.get('edition'),'s3_available':plan.get('s3_available'),
                'capability_change':plan.get('capability_change'),'message':message}

def emit_receipt_template(candidate,target,out):
    """U5: write the component-review skeleton (added files + real hashes + empty reason)."""
    candidate=st.no_links(candidate).resolve();target=st.no_links(target).resolve()
    out=st.no_links(Path(out)).resolve()
    if out.is_relative_to(candidate) or out.is_relative_to(target):
        raise ValueError('Write the receipt template outside the candidate and the target core')
    if out.exists():
        raise ValueError('Output must not exist; use a new file name')
    cmeta=parse_json((candidate/'CORE.json').read_bytes())
    old=parse_json((target/'CORE.json').read_bytes())
    if not isinstance(cmeta.get('files'),dict) or not isinstance(old.get('files'),dict):
        raise ValueError('Both directories need a readable CORE.json manifest')
    added=sorted(set(cmeta['files'])-set(old['files']))
    template={'schema':1,'purpose':'component-review','version':cmeta['version'],
              'reviewed_by':'','reason':'','files':{rel:cmeta['files'][rel] for rel in added}}
    st.atomic_bytes(out,st.json_bytes(template))
    return {'status':'WROTE_TEMPLATE','out':str(out),'added':len(added),'files':added,
            'next_step':('填写 reviewed_by 与 reason（键集合与摘要已由脚本算好，不要改动）后，'
                         '用 plan-install --reviewed-manifest <该文件> 重跑。')}

class UpdateArgumentParser(argparse.ArgumentParser):
    """U6: cross-version CLI shapes changed (e.g. old `--candidate`), so every argparse
    error should point at the change log instead of leaving historical scripts to fail blind."""
    def error(self,message):
        message+=('\n提示：跨版本升级时 CLI 参数形态可能变化，见 references/compatibility-matrix.md '
                  '的“CLI 参数变更记录”。')
        super().error(message)


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    p=UpdateArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('check');q.add_argument('--core',type=Path,default=CORE)
    mode=q.add_mutually_exclusive_group();mode.add_argument('--online',action='store_true');mode.add_argument('--snapshot',type=Path)
    q.add_argument('--stable-only',action='store_true',help='只比较正式发布；默认渠道同时包含预发布')
    q.add_argument('--include-prerelease',action='store_true',help='(兼容旧参数) 预发布默认已包含')
    d=sub.add_parser('download',help='在用户明确授权后下载 Release 附件（Python urllib，固定来源与大小上限）')
    d.add_argument('url');d.add_argument('out',type=Path)
    d.add_argument('--sha256',default=None,help='期望 SHA-256，不匹配则拒绝')
    d.add_argument('--max-bytes',type=int,default=64*1024*1024)
    d.add_argument('--force',action='store_true',help='允许覆盖已存在的输出文件')
    r=sub.add_parser('verify-remote-tag',help='只读核验远端 tag 的 CORE.json 是否与本机候选一致（发布前预检）')
    r.add_argument('--tag',required=True);r.add_argument('--core',type=Path,default=CORE)
    for name in ('plan-install','install'):
        q=sub.add_parser(name);q.add_argument('candidate',type=Path,nargs='?')
        q.add_argument('--candidate',dest='candidate_opt',type=Path,
                       help='兼容旧写法的同义参数；与位置参数二选一')
        q.add_argument('--target',type=Path,required=True,help='真实待更新技能根目录（必填，避免误用脚本所在目录）')
        q.add_argument('--expected-version',required=True)
        q.add_argument('--allow-dev',action='store_true')
        q.add_argument('--reviewed-manifest',type=Path,default=None,
                       help='新增组件的迁移审查收据（schema 1/component-review），有新增文件时必填')
        q.add_argument('--repair-host-rewrite',action='store_true',
                       help='（U1/W1）目标核心被宿主改写时：允许用候选包中的同名官方文件覆盖这些文件后继续升级；'
                            '只影响“与自身清单不符”的文件，结束后仍做整目录核验；默认不启用')
        if name=='install':q.add_argument('--plan-id',required=True)
    t=sub.add_parser('emit-receipt-template',
                     help='按新增文件生成 component-review 收据骨架（摘要由脚本计算，你只填 reviewed_by/reason）')
    t.add_argument('--candidate',type=Path,required=True);t.add_argument('--target',type=Path,required=True)
    t.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.command in ('plan-install','install'):
        if a.candidate is None and a.candidate_opt is None:
            p.error('需要候选目录：位置参数 <candidate> 或 --candidate <目录> 二选一')
        a.candidate=a.candidate if a.candidate is not None else a.candidate_opt
    if a.command=='check':
        if a.stable_only and a.include_prerelease:p.error('--stable-only conflicts with --include-prerelease')
        result=check(a.core,a.online,a.snapshot,'stable' if a.stable_only else 'all')
    elif a.command=='download':result=download_asset(a.url,a.out,a.sha256,a.max_bytes,a.force)
    elif a.command=='verify-remote-tag':result=remote_tag_check(a.tag,a.core)
    elif a.command=='plan-install':result=install_plan(a.candidate,a.target,a.allow_dev,a.expected_version,
                                                       a.reviewed_manifest,repair_host_rewrite=a.repair_host_rewrite)
    elif a.command=='emit-receipt-template':result=emit_receipt_template(a.candidate,a.target,a.out)
    else:result=install(a.candidate,a.target,a.plan_id,a.allow_dev,a.expected_version,a.reviewed_manifest,
                        repair_host_rewrite=a.repair_host_rewrite)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status') in ('VALIDATION_ERROR','LOCAL_CORE_INVALID','RATE_LIMITED','NETWORK_ERROR',
                                'TIMEOUT','TLS_ERROR','HTTP_ERROR','NOT_FOUND','INCOMPLETE'):
        return 1
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as ex:
        print('UPDATE_STOPPED: '+str(ex),file=sys.stderr);raise SystemExit(1)
