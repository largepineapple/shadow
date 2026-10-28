import argparse
import json
from pathlib import Path
from .models import validate_request
from .storage import Storage
from .tools import Tools
from .agent import Agent
from .mock_policy import MockPolicy
from .llm_client import LiveClient
from .trace import Trace


def main():
    parser=argparse.ArgumentParser(description='Synthetic material scheduling agent; local drafts only')
    parser.add_argument('--mode',choices=['mock','live'],required=True)
    parser.add_argument('--input',required=True)
    parser.add_argument('--db',default='agent.sqlite')
    parser.add_argument('--trace',required=True)
    parser.add_argument('--output')
    parser.add_argument('--inject-save-failure',action='store_true')
    parser.add_argument('--max-steps',type=int,default=8)
    parser.add_argument('--max-tool-calls',type=int,default=10)
    args=parser.parse_args()
    storage=None
    trace=Trace(args.mode,'uninitialized','invalid-request')
    try:
        r=validate_request(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
        client=MockPolicy(r) if args.mode=='mock' else LiveClient()
        trace=Trace(args.mode,client.model,r['request_id'])
        storage=Storage(args.db)
        agent=Agent(Tools(r,storage,inject_failure=args.inject_save_failure),client,trace,args.max_steps,args.max_tool_calls)
        result=agent.run()
    except Exception as exc:
        result={'status':'incomplete','published':False,'reason':str(exc),'materials':[]}
    finally:
        if storage: storage.close()
    trace.save(args.trace,result)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)
    print(rendered)
    if args.output:
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        Path(args.output).write_text(rendered,encoding='utf-8')
    return 1 if result['status']=='incomplete' else 0


if __name__=='__main__':
    raise SystemExit(main())
