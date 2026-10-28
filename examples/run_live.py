"""Run real-model acceptance cases. Credentials come only from process environment."""
import argparse
import json
from pathlib import Path
import tempfile
import time
from src.agent import Agent
from src.llm_client import LiveClient
from src.models import validate_request
from src.storage import Storage
from src.tools import Tools
from src.trace import Trace

CASES = {
    'normal': ('normal', 'completed', 'saved', 1),
    'missing': ('missing', 'needs_information', 'not_saved', 0),
    'risk': ('risk', 'blocked', 'not_saved', 0),
    'conflict': ('conflict', 'needs_confirmation', 'not_saved', 0),
    'confirmed_alternative': ('confirmed_alternative', 'completed', 'saved', 1),
    'duplicate': ('normal', 'completed', 'existing', 1),
    'save_failure': ('save_failure', 'save_failed', 'failed', 0),
    'reoccupied': ('conflict', 'needs_confirmation', 'not_saved', 1),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', choices=list(CASES), default=list(CASES))
    parser.add_argument('--prefix', default='deepseek')
    args = parser.parse_args()
    if not args.prefix.replace('_', '').replace('-', '').isalnum():
        parser.error('prefix must be a simple filename component')
    client = LiveClient()
    summary = {'mode': 'live', 'model': client.model, 'endpoint': client.base, 'cases': []}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        for name in args.cases:
            source, expected, draft_status, count = CASES[name]
            request = validate_request(json.loads(Path(f'examples/inputs/{source}.json').read_text()))
            # Duplicate reuses the normal DB; seed through a real agent if normal was not selected.
            db = Path(directory) / ('normal.sqlite' if name == 'duplicate' else name + '.sqlite')
            if name == 'duplicate' and not db.exists():
                store = Storage(str(db))
                seed_trace = Trace('live', client.model, request['request_id'])
                seed = Agent(Tools(request, store), client, seed_trace).run()
                seed_trace.save(f'examples/traces/{args.prefix}_duplicate_seed_live.json', seed)
                store.close()
            store = Storage(str(db))
            if name == 'reoccupied':
                seed_request = json.loads(Path('examples/inputs/confirmed_alternative.json').read_text())
                seeded = Tools(seed_request, store).save_draft('M01', seed_request['confirmed_alternative_time'])
                if not seeded['ok']:
                    raise RuntimeError('Could not seed occupied candidate')
            trace = Trace('live', client.model, request['request_id'])
            trace.value['acceptance_case'] = name
            if name == 'reoccupied':
                trace.value['fixture'] = 'Local deterministic fixture occupies 19:00 before the live run'
            case_start = time.perf_counter()
            result = Agent(Tools(request, store, inject_failure=name == 'save_failure'), client, trace).run()
            draft_count = len(store.drafts())
            store.close()
            trace.save(f'examples/traces/{args.prefix}_{name}_live.json', result)
            Path(f'examples/outputs/{args.prefix}_{name}_live.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            checks = {
                'status': result['status'] == expected,
                'draft_status': result['materials'][0]['draft_status'] == draft_status,
                'db_count': draft_count == count,
                'not_published': result['published'] is False,
                'real_loop': any(s['action'] not in ('model_error', 'finish') and s['next_action'] is not None for s in trace.value['steps']),
            }
            if name == 'missing':
                checks['active_lookup'] = sum(s['action'] == 'get_material' for s in trace.value['steps']) >= 2
            if name in ('conflict', 'reoccupied'):
                hour = '19' if name == 'conflict' else '20'
                checks['alternative'] = result['materials'][0]['suggested_time'] == f'2026-11-03T{hour}:00:00+08:00'
            entry = {'name': name, 'status': result['status'], 'draft_status': result['materials'][0]['draft_status'], 'db_count': draft_count, 'checks': checks, 'passed': all(checks.values()), 'elapsed_seconds': round(time.perf_counter()-case_start, 3), 'actions': [s['action'] for s in trace.value['steps']]}
            summary['cases'].append(entry)
            summary['elapsed_seconds'] = round(time.perf_counter()-started, 3)
            Path(f'examples/{args.prefix}_live_results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            if result['status'] == 'incomplete' and all(s['action'] == 'model_error' for s in trace.value['steps']):
                print('Stopping after model connection/response failure; inspect generated trace.', flush=True)
                break
    return 0 if len(summary['cases']) == len(args.cases) and all(c['passed'] for c in summary['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
