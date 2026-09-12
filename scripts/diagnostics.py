"""Read-only configuration and optional record diagnostics.

本模块主要被 `experience.py doctor` 调用，不作为独立诊断入口的替代；
如需直接运行，可用 `python -B scripts/diagnostics.py [--profile <目录>] [--deep]`，
输出与 experience.py doctor 相同。
"""
import argparse
import json
import sys
from pathlib import Path
import experience as e
import core_package as cp
import safe_store as st

def _specific_next_step(exc, fallback):
    """Map common configuration failures to concrete next steps; never leaks message text."""
    text=str(exc).lower()
    if any(k in text for k in ('unsupported profile schema','unknown installation schema','policy mismatch','schema')):
        return '版本/格式不兼容：核对档案 schema 与本核心最低读取版本（见 references/compatibility-matrix.md）；保留原目录与备份，按兼容升级路径处理，勿覆盖重建。'
    if any(k in text for k in ('capacity','too large','file too large','exceed','too many','max_file','max_total')):
        return '容量超限或超出当前限制：核对备份与档案大小，必要时分档案或归档；不删除原件重试。'
    if any(k in text for k in ('symlink','reparse','hard link','symbolic link')):
        return '路径包含链接：保留原目录，不自动解析或放开链接保护；核对宿主允许的独立非链接绝对路径，已有档案用显式 --profile 检查，通过后再绑定。'
    if 'pending' in text:
        return '存在未决事务：核对事务与备份，按 recover 流程处理，不新建空档案掩盖。'
    return fallback

SKILL_ROOT_CANDIDATES=('.codex/skills','.agents/skills','.qwenworkcn/skills','.codebuddy/skills',
                       '.claude/skills','.cursor/skills','.trae/skills')

def skill_roots(home=None):
    """Where clients keep skills. Known roots first (they work even when listing the user
    profile is denied), then a best-effort sweep of visible/hidden siblings."""
    home=Path(home) if home else Path.home()
    roots=[]
    for rel in SKILL_ROOT_CANDIDATES:
        candidate=home/rel
        try:
            if candidate.is_dir():
                roots.append(candidate)
        except OSError:
            continue
    try:
        for entry in home.iterdir():
            candidate=entry/'skills'
            try:
                if candidate.is_dir() and candidate not in roots:
                    roots.append(candidate)
            except OSError:
                continue
    except OSError:
        pass
    return roots

def other_installations(current=None):
    """037 (2026-09-12): one machine can hold several clients, each with its own copy.
    A real test machine had `.codex\\skills` on 0.21.5 and `.qwenworkcn\\skills` on 0.22.6
    sharing one profile - silently checking the wrong copy made a whole report unusable.
    Read-only, and every step tolerates a denied directory."""
    try:
        current=Path(current).resolve() if current else None
    except OSError:
        current=None
    found={}

    def consider(path):
        try:
            if not (path/'CORE.json').is_file() or not (path/'SKILL.md').is_file():
                return
            meta=json.loads((path/'CORE.json').read_text(encoding='utf-8'))
            resolved=path.resolve()
        except (OSError,ValueError):
            return
        found[str(resolved)]={'version':meta.get('version'),
                              'canonical_name':meta.get('canonical_name'),
                              'is_checked_here':resolved==current}

    for root in skill_roots():
        try:
            children=list(root.iterdir())
        except OSError:
            continue
        for child in children:
            consider(child)
    if current is not None:
        consider(current)
    rows=[dict(path=path,**facts) for path,facts in sorted(found.items())]
    result={'count':len(rows),'installs':rows,'read_only':True}
    versions=sorted({row['version'] for row in rows if row.get('version')})
    if len(rows)>1:
        result['note']=('本机存在多份安装：每个客户端各装一份属预期行为，但请先确认本次检查/升级的是哪一份。')
        if len(versions)>1:
            result['version_mismatch']=versions
            result['note']+=('检测到版本不一致（'+'、'.join(versions)+'）：不同版本读同一份档案时，'
                             '召回与校验结论可能对不上号。')
    return result


def human(report):
    """Plain-text rendering of a doctor report for people. JSON stays the default."""
    lines=['配置诊断：%s（只读）' % report.get('status','UNKNOWN')]
    checks=report.get('checks') or {}
    if checks:
        lines.append('检查项：'+'，'.join('%s=%s' % (k,v) for k,v in sorted(checks.items())))
    for key,label in (('write_access','写入权限'),('core_write_access','核心写入权限'),
                      ('persistence','跨会话持久性')):
        if key in report:
            lines.append('%s：%s' % (label,report[key]))
    modules=report.get('optional_modules') or {}
    if modules:
        if 'error' in modules:
            lines.append('可选模块：读取失败（%s）' % modules['error'])
        else:
            lines.append('版本形态：edition=%s，可选 S3=%s%s' % (
                modules.get('edition'),'启用' if modules.get('enabled') else '未启用',
                '' if modules.get('s3_available') else '（本包未附带该模块）'))
    installs=report.get('installations') or {}
    if installs.get('count'):
        lines.append('本机安装：共 %d 份%s' % (
            installs['count'],
            ('；版本不一致：'+'、'.join(installs.get('version_mismatch') or []))
            if installs.get('version_mismatch') else ''))
        for row in installs.get('installs') or []:
            lines.append('  - %s（%s）%s' % (row.get('path'),row.get('version'),
                                             ' ← 本次检查对象' if row.get('is_checked_here') else ''))
    if report.get('next_step'):
        lines.append('下一步：'+str(report['next_step']))
    if report.get('status')=='OK':
        lines.append('说明：OK 只代表配置检查通过，不等于全部数据功能已就绪；'
                     '实际写入能力以正常写入与读回结果为准。')
    return '\n'.join(lines)


def doctor(profile=None, deep=False, core=e.CORE, allow_host_files=False):
    report={'status':'OK','checks':{},'read_only':True,'write_access':'not-tested',
            'core_write_access':'not-tested','persistence':'unknown',
            'environment':e.current_environment(),'record_contents_included':False,'context':None}
    try:
        report['core']=cp.verify(core,allow_host_files=allow_host_files)
        report['checks']['core']='verified'
    except (ValueError,OSError,KeyError,TypeError,AttributeError):
        report.update(status='CORE_INVALID',next_step='重新核对核心清单与安装来源，保留私人档案。')
        return report
    try:
        import optional_features as features
        report['optional_modules']=features.status(core)
    except (ValueError,OSError,KeyError,TypeError,ImportError) as ex:
        report['optional_modules']={'error':str(ex)[:200]}
    report['installations']=other_installations(core)
    if sys.version_info<(3,10):
        report.update(status='RUNTIME_UNSUPPORTED',next_step='使用 Python 3.10 或以上。');return report
    try:
        report['context']=e.active_context()
    except ValueError:
        report.update(status='BINDING_INVALID',
                      next_step='REVIEW_EVOLUTION_CLIENT 与 REVIEW_EVOLUTION_ACCOUNT 需同时设置或同时不设置。')
        return report
    if profile is None and report['context'] is not None:
        try:
            profile=e.resolve_context_root(report['context'])
        except PermissionError:
            report.update(status='ACCESS_DENIED',next_step='无法读取账号绑定或目标目录；检查宿主访问权限，保留已有档案。')
            return report
        except (OSError,KeyError,TypeError,AttributeError):
            report.update(status='BINDING_INVALID',next_step='账号绑定读取失败；核对已有绑定及备份，不创建空档案替代。')
            return report
        except ValueError as exc:
            if not str(exc).startswith('No context binding for '):
                report.update(status='BINDING_INVALID',next_step=_specific_next_step(exc,'账号绑定无效；核对已有绑定及备份，不创建空档案替代。'))
                return report
            report.update(status='UNBOUND',
                          next_step='该客户端/账号尚无档案绑定：绑定已有档案，或 init 后 bind --client <客户端> --account <账号> <档案>。')
            return report
    if profile is None:
        try:
            binding=e.read(e.binding_path())
            if not isinstance(binding,dict) or binding.get('schema')!=e.FORMAT or not isinstance(binding.get('profile_root'),str) or not binding['profile_root']:
                raise ValueError('Invalid binding')
            profile=binding['profile_root']
        except FileNotFoundError:
            report.update(status='UNBOUND',next_step='已有档案请绑定；仅全新使用时创建独立档案再绑定。');return report
        except PermissionError:
            report.update(status='ACCESS_DENIED',next_step='无法读取安装绑定；检查客户端目录访问权限，不覆盖原文件。');return report
        except (ValueError,OSError,KeyError,TypeError,AttributeError) as exc:
            report.update(status='BINDING_INVALID',next_step=_specific_next_step(exc,'检查本客户端绑定，勿覆盖或删除原私人档案。'));return report
    try:
        root=e.profile_root(profile)
        if not root.exists():
            report.update(status='PROFILE_MISSING',next_step='核对已有档案位置或备份，不用空档案覆盖。');return report
        if st.pending(root):
            report.update(status='PENDING_TRANSACTION',next_step='核对未完成事务及备份，按 recover 流程恢复后重试。');return report
        meta=e.info(root)
        report['checks']['profile']='metadata-verified'
        report['revision']=meta['revision']
        report['records_validation']='not-requested'
        if deep:
            q=e.query(root);e._query_s3(root);e.s1_metrics(root);e.s2_metrics(root)
            e.load_update_ledger(root);e.trusted_sources_view(root)
            report['records_validation']='passed'
            report['counts']={'records':len(q['records']),'effective_preferences':len(q['effective_preferences'])}
        report['next_step']='配置检查通过；实际写入能力以正常写入结果为准。'
    except FileNotFoundError:
        report.update(status='PROFILE_INVALID',next_step='已有目录缺少必要文件或检查时发生变化；保留目录并核对备份。')
    except PermissionError:
        report.update(status='ACCESS_DENIED',next_step='确认客户端允许访问该私人目录；尚未判断数据完整性。')
    except (ValueError,OSError,KeyError,TypeError,AttributeError) as exc:
        report.update(status='PROFILE_INVALID',next_step=_specific_next_step(exc,'保留原目录，核对格式、策略和备份；不要直接重建覆盖。'))
    return report


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser(description='只读配置诊断（被 experience.py doctor 调用；也可直接运行）')
    p.add_argument('--profile',default=None,help='私人档案目录；缺省读取本机绑定')
    p.add_argument('--deep',action='store_true',help='深度校验（查询/指标/更新账本/可信来源只读调用）')
    a=p.parse_args()
    print(json.dumps(doctor(a.profile,a.deep),ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('DIAGNOSTICS_STOPPED: '+str(exc),file=sys.stderr);raise SystemExit(1)


