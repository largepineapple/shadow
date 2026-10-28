from concurrent.futures import ThreadPoolExecutor
from src.storage import Storage
from src.tools import Tools
from tests.test_tools import request


def test_concurrent_duplicate(tmp_path):
    path=str(tmp_path/'concurrent.sqlite')
    Storage(path).close()
    def save(_):
        store=Storage(path)
        result=Tools(request(),store).save_draft('M05',request()['requested_time'])
        store.close()
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(save,range(2)))
    assert sorted(r['data']['draft_status'] for r in results)==['existing','saved']
    assert results[0]['data']['draft_id']==results[1]['data']['draft_id']


def test_risks_cannot_be_saved(tmp_path):
    store=Storage(str(tmp_path/'risk.sqlite'))
    for name,mid in [('missing','M02'),('risk','M03'),('review','M04')]:
        t=Tools(request(name),store)
        assert t.save_draft(mid,t.request['requested_time'])['error']['code']=='REVIEW_NOT_APPROVED'
    assert not store.drafts()
    store.close()


def test_soft_adjustment(tmp_path):
    from src.agent import Agent
    from src.mock_policy import MockPolicy
    from src.trace import Trace
    r=request('conflict');r['time_requirement']='soft'
    store=Storage(str(tmp_path/'soft.sqlite'))
    result=Agent(Tools(r,store),MockPolicy(r),Trace('mock','test','soft')).run()
    assert result['status']=='completed'
    assert result['materials'][0]['suggested_time'].endswith('19:00:00+08:00')
    assert result['materials'][0]['time_change_reason']
    store.close()
