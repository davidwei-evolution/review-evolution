"""Fixed release-gate check for Windows one-click launchers (.bat/.cmd). Read-only; never executes them.

Enforces the mechanically checkable part of the delivery rule adopted 2026-09-10:
CRLF line endings, no UTF-8 BOM, every exit path preceded by `pause`, and at least one
redirect that persists a result/log file. It does NOT prove the launcher works on a real
machine: "双击可用且有产出" still needs a real run, see references/release-check.md.
"""
import argparse,json,re,sys,zipfile
from pathlib import Path

SUFFIXES=('.bat','.cmd')
PAUSE=re.compile(r'(?im)^\s*pause\b')
EXIT=re.compile(r'(?im)^\s*exit\b')
PERSIST=re.compile(r'>>?\s*"?[^\s"<>|&]*\.(?:md|txt|log)\b|>>?\s*"%[A-Za-z_][A-Za-z0-9_]*%"',re.I)
LOOKBACK=12

def analyze(data):
    if not data:return ['empty-launcher']
    rules=set()
    if data.startswith(b'\xef\xbb\xbf'):rules.add('utf8-bom')
    if not data.endswith(b'\n'):rules.add('missing-trailing-newline')
    if data.replace(b'\r\n',b'').replace(b'\r',b'').count(b'\n'):rules.add('bare-lf-line-endings')
    try:text=data.decode('utf-8')
    except UnicodeDecodeError:return sorted(rules|{'invalid-utf8'})
    if not PAUSE.search(text):rules.add('no-pause')
    lines=text.splitlines()
    for num,line in enumerate(lines):
        if EXIT.match(line) and not any(PAUSE.match(x) for x in lines[max(0,num-LOOKBACK):num]):
            rules.add('exit-without-pause');break
    if not PERSIST.search(text):rules.add('no-persisted-output')
    return sorted(rules)

def collect(target):
    target=Path(target)
    if target.is_dir():
        return [(p.relative_to(target).as_posix(),p.read_bytes())
                for p in sorted(target.rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts and p.suffix.lower() in SUFFIXES]
    if target.is_file() and target.suffix.lower()=='.zip':
        with zipfile.ZipFile(target) as z:
            return [(i.filename,z.read(i)) for i in z.infolist()
                    if not i.is_dir() and Path(i.filename).suffix.lower() in SUFFIXES]
    raise ValueError('Expected a folder or a zip: '+str(target))

def check(target):
    files=collect(target)
    findings=[{'file':rel,'rules':analyze(data)} for rel,data in files]
    findings=[f for f in findings if f['rules']]
    result={'schema':1,'target':str(target),'launchers':len(files),
            'status':'PASS' if not findings else 'FAIL','findings':findings,
            'limits':'Static rules only; a real double-click or AI run on the target machine is still required.'}
    if not files:result['note']='No .bat/.cmd in target; nothing to check.'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=Path)
    args=parser.parse_args()
    try:
        report=check(args.target)
        print(json.dumps(report,ensure_ascii=False,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);raise SystemExit(1)
    raise SystemExit(1 if report['findings'] else 0)
