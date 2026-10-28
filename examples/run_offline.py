"""Generate offline evidence using fresh databases; never labels mock as live."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    started=time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        for name in ['normal','missing','risk','review','conflict','confirmed_alternative','save_failure','duplicate','limits','reoccupied']:
            source='normal' if name in ('duplicate','limits') else 'conflict' if name=='reoccupied' else name
            db=str(Path(directory)/('normal' if name=='duplicate' else name))
            if name=='reoccupied':
                from src.storage import Storage
                from src.tools import Tools
                store=Storage(db)
                r=json.loads(Path('examples/inputs/confirmed_alternative.json').read_text())
                assert Tools(r,store).save_draft('M01',r['confirmed_alternative_time'])['ok']
                store.close()
            command=[sys.executable,'-m','src.main','--mode','mock','--input',f'examples/inputs/{source}.json','--db',db,'--trace',f'examples/traces/{name}_mock.json','--output',f'examples/outputs/{name}_mock.json']
            if name=='save_failure': command.append('--inject-save-failure')
            if name=='limits': command+=['--max-steps','1']
            run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            if run.returncode != (1 if name=='limits' else 0): raise RuntimeError(run.stderr or run.stdout)
            result=json.loads(run.stdout)
            print(name+': '+result['status']+' / '+result['materials'][0]['draft_status'])
    run=subprocess.run([sys.executable,'-m','pytest','-q'],capture_output=True,text=True)
    report='Command: python -m pytest -q\nMode: mock/offline only\n'+run.stdout+run.stderr+f'\nEvidence runner elapsed_seconds: {time.perf_counter()-started:.3f}\n'
    Path('examples/test_results.txt').write_text(report,encoding='utf-8')
    print(report)
    return run.returncode


if __name__=='__main__': raise SystemExit(main())
