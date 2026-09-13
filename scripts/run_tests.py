"""Run tests in a verified manifest-only copy, including on host-managed installs."""
from pathlib import Path
import argparse,json,subprocess,sys,tempfile
import core_package as cp
import safe_store as st

def prepare(root,destination):
    root=Path(root)
    cp.verify(root,allow_host_files=True)
    meta=json.loads((root/'CORE.json').read_text(encoding='utf-8'))
    destination=Path(destination)
    destination.mkdir()
    for rel in [*meta['files'],'CORE.json']:
        data=st.inside(root,rel).read_bytes()
        if rel!='CORE.json' and st.digest(data)!=meta['files'][rel]:
            raise ValueError('Source changed during test snapshot')
        target=destination/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
    cp.verify(destination)
    return destination

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--pattern',default='test*.py')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='review-tests-') as directory:
        core=prepare(args.root,Path(directory)/'core')
        return subprocess.call([sys.executable,'-B','-m','unittest','discover','-s','tests','-p',args.pattern],cwd=core)

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('TEST_SOURCE_INVALID: '+str(exc),file=sys.stderr);sys.exit(1)

