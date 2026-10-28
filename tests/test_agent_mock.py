import pytest
from src.agent import Agent
from src.mock_policy import MockPolicy
from src.trace import Trace
from src.tools import Tools
from src.storage import Storage
from tests.test_tools import request


def run(tmp_path, name, failure=False, client=None, steps=8, calls=10, store=None):
    r=request(name)
    store=store or Storage(str(tmp_path/'agent.sqlite'))
    t=Tools(r,store,inject_failure=failure)
    trace=Trace('mock','test',r['request_id'])
    result=Agent(t,client or MockPolicy(r),trace,steps,calls).run()
    return result,trace,store


@pytest.mark.parametrize('name,status',[('normal','completed'),('missing','needs_information'),('risk','blocked'),('review','needs_confirmation'),('conflict','needs_confirmation'),('confirmed_alternative','completed')])
def test_scenarios(tmp_path,name,status):
    result,trace,store=run(tmp_path,name)
    assert result['status']==status
    assert result['materials'][0]['outcome_status']==status
    assert result['published'] is False
    if name=='missing': assert sum(s['action']=='get_material' for s in trace.value['steps'])==2
    if name=='conflict':
        assert result['materials'][0]['suggested_time'].endswith('19:00:00+08:00')
        assert result['materials'][0]['draft_status']=='not_saved'
    assert len(store.drafts()) == (1 if status=='completed' else 0)
    store.close()


def test_save_failure(tmp_path):
    result,_,store=run(tmp_path,'normal',True)
    assert result['status']=='save_failed'
    assert result['materials'][0]['draft_status']=='failed'
    assert not store.drafts()
    store.close()


@pytest.mark.parametrize('steps,calls',[(1,10),(8,0)])
def test_limits(tmp_path,steps,calls):
    result,_,store=run(tmp_path,'normal',steps=steps,calls=calls)
    assert result['status']=='incomplete'
    assert 'limit' in result['reason']
    store.close()


def test_duplicate(tmp_path):
    a,_,store=run(tmp_path,'normal')
    b,_,_=run(tmp_path,'normal',store=store)
    assert b['materials'][0]['draft_status']=='existing'
    assert a['materials'][0]['draft_id']==b['materials'][0]['draft_id']
    assert len(store.drafts())==1
    store.close()


def test_reoccupied_alternative(tmp_path):
    store=Storage(str(tmp_path/'occupied.sqlite'))
    t=Tools(request('confirmed_alternative'),store)
    assert t.save_draft('M01','2026-11-03T19:00:00+08:00')['ok']
    result,_,_=run(tmp_path,'conflict',store=store)
    assert result['status']=='needs_confirmation'
    assert result['materials'][0]['suggested_time'].endswith('20:00:00+08:00')
    assert len(store.drafts())==1
    store.close()


def test_no_suggestion_permission(tmp_path):
    r=request('conflict'); r['allow_alternative_suggestion']=False
    store=Storage(str(tmp_path/'no.sqlite'))
    result=Agent(Tools(r,store),MockPolicy(r),Trace('mock','test','no')).run()
    assert result['materials'][0]['suggested_time'] is None
    store.close()


class Dishonest:
    def choose(self,messages): return 'finish',{'decision_basis':'Published and saved successfully'},'bad'


def test_untrusted_finish(tmp_path):
    result,_,store=run(tmp_path,'normal',client=Dishonest())
    assert result['status']=='incomplete'
    assert result['materials'][0]['draft_status']=='not_saved'
    assert not result['published']
    store.close()
class InvalidAction:
    def choose(self,messages): return 'save_draft',{'material_id':'M05','proposed_time':42},'invalid'


def test_invalid_action_retry_bounded(tmp_path):
    result,trace,store=run(tmp_path,'normal',client=InvalidAction())
    assert result['status']=='incomplete'
    assert len(trace.value['steps'])==2
    assert not store.drafts()
    store.close()


def test_multi_material_serial_conflict(tmp_path):
    r=request('normal');r['material_ids']=['M05','M01']
    store=Storage(str(tmp_path/'batch.sqlite'))
    result=Agent(Tools(r,store),MockPolicy(r),Trace('mock','test','batch'),max_steps=12).run()
    assert result['status']=='needs_confirmation'
    assert result['materials'][0]['draft_status']=='saved'
    assert result['materials'][1]['draft_status']=='not_saved'
    assert result['materials'][0]['outcome_status']=='completed'
    assert result['materials'][1]['outcome_status']=='needs_confirmation'
    assert len(store.drafts())==1
    store.close()


@pytest.mark.parametrize('material_id,outcome',[
    ('M03','blocked'), ('M02','needs_information'), ('M04','needs_confirmation'),
])
def test_mixed_batch_preserves_saved_outcome(tmp_path,material_id,outcome):
    r=request('normal');r['material_ids']=['M05',material_id]
    store=Storage(str(tmp_path/'mixed.sqlite'))
    result=Agent(Tools(r,store),MockPolicy(r),Trace('mock','test','mixed')).run()
    assert result['status']==outcome
    saved,other=result['materials']
    assert saved['outcome_status']=='completed'
    assert saved['draft_status']=='saved'
    assert saved['draft_id']==store.drafts()[0]['id']
    assert other['outcome_status']==outcome
    assert other['draft_status']=='not_saved'
    assert len(store.drafts())==1
    assert result['published'] is False
    store.close()


def test_budget_exhaustion_preserves_completed_item(tmp_path):
    r=request('normal');r['material_ids']=['M05','M01']
    store=Storage(str(tmp_path/'partial.sqlite'))
    result=Agent(Tools(r,store),MockPolicy(r),Trace('mock','test','partial'),max_steps=4).run()
    assert result['status']=='incomplete'
    assert result['materials'][0]['outcome_status']=='completed'
    assert result['materials'][0]['draft_status']=='saved'
    assert result['materials'][1]['outcome_status']=='incomplete'
    assert len(store.drafts())==1
    store.close()
