"""Read-only configuration and optional record diagnostics.

本模块主要被 `experience.py doctor` 调用，不作为独立诊断入口的替代；
如需直接运行，可用 `python -B scripts/diagnostics.py [--profile <目录>] [--deep]`，
输出与 experience.py doctor 相同。
"""
import argparse
import json
import sys
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
    if 'pending' in text:
        return '存在未决事务：核对事务与备份，按 recover 流程处理，不新建空档案掩盖。'
    return fallback

def doctor(profile=None, deep=False, core=e.CORE):
    report={'status':'OK','checks':{},'read_only':True,'write_access':'not-tested',
            'environment':e.current_environment(),'record_contents_included':False}
    try:
        report['core']=cp.verify(core)
        report['checks']['core']='verified'
    except (ValueError,OSError,KeyError,TypeError,AttributeError):
        report.update(status='CORE_INVALID',next_step='重新核对核心清单与安装来源，保留私人档案。')
        return report
    if sys.version_info<(3,10):
        report.update(status='RUNTIME_UNSUPPORTED',next_step='使用 Python 3.10 或以上。');return report
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
            q=e.query(root);e.query_s3(root);e.s1_metrics(root);e.s2_metrics(root)
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


