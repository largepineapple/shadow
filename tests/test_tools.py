import json
from pathlib import Path
import pytest
from src.models import validate_request
from src.storage import Storage
from src.tools import Tools


def request(name='normal'):
    return json.loads(Path(f'examples/inputs/{name}.json').read_text())


@pytest.fixture
def tools(tmp_path):
    store = Storage(str(tmp_path / 'test.sqlite'))
    yield Tools(request(), store)
    store.close()


def test_normal_and_duplicate(tools):
    a = tools.save_draft('M05', tools.request['requested_time'])
    b = tools.save_draft('M05', tools.request['requested_time'])
    assert a['data']['draft_status'] == 'saved'
    assert b['data']['draft_status'] == 'existing'
    assert a['data']['draft_id'] == b['data']['draft_id']
    assert len(tools.storage.drafts()) == 1


def test_rules(tools):
    assert tools.check_rules('M02')['data']['missing_fields'] == ['copyright_status']
    assert tools.check_rules('M03')['data']['review_status'] == 'blocked'
    assert tools.check_rules('M04')['data']['review_status'] == 'review_required'
    assert not tools.get_material('unknown')['ok']


def test_conflict_confirmation(tools):
    tools.request = request('conflict')
    slots = tools.query_slots('short_video', tools.request['requested_time'])['data']
    assert not slots['available']
    assert slots['alternatives'][0].endswith('19:00:00+08:00')
    assert not tools.save_draft('M01', slots['alternatives'][0])['ok']
    tools.request = request('confirmed_alternative')
    assert tools.save_draft('M01', tools.request['confirmed_alternative_time'])['ok']


def test_failure_and_content_conflict(tools):
    tools.inject_failure = True
    assert tools.save_draft('M05', tools.request['requested_time'])['error']['code'] == 'SAVE_UNAVAILABLE'
    assert tools.storage.drafts() == []
    tools.inject_failure = False
    tools.save_draft('M05', tools.request['requested_time'])
    tools.request['requested_time'] = '2026-11-03T22:00:00+08:00'
    assert tools.save_draft('M05', tools.request['requested_time'])['error']['code'] == 'REQUEST_CONTENT_CONFLICT'


def test_intervals_and_batch(tools):
    assert tools.conflicts('short_video', '2026-11-03T10:30:00+00:00')
    assert not tools.conflicts('short_video', '2026-11-03T19:00:00+08:00')
    tools.request['material_ids'].append('M01')
    assert tools.save_draft('M05', tools.request['requested_time'])['ok']
    assert tools.save_draft('M01', tools.request['requested_time'])['error']['code'] == 'SLOT_CONFLICT'


def test_input_validation():
    r = request()
    validate_request(r)
    r['requested_time'] = '2026-11-03T20:00:00'
    with pytest.raises(ValueError): validate_request(r)
