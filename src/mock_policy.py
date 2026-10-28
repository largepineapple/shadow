import json


class MockPolicy:
    model = 'deterministic-mock-no-LLM'

    def __init__(self, request):
        self.request = request

    def choose(self, messages):
        history = []
        for msg in messages:
            if msg['role'] == 'tool':
                history.append((msg['name'], json.loads(msg['content'])))
        for mid in self.request['material_ids']:
            # Mock is deliberately deterministic and never used by live mode.
            own = [(n,o) for n,o in history if o.get('_material_id') == mid]
            names = [n for n,o in own]
            if 'get_material' not in names: return 'get_material', {'material_id':mid}, 'mock'
            if 'check_rules' not in names: return 'check_rules', {'material_id':mid}, 'mock'
            review = next(o['data'] for n,o in own if n == 'check_rules')
            if review['review_status'] == 'insufficient_data' and names.count('get_material') < 2:
                return 'get_material', {'material_id':mid}, 'mock'
            if review['review_status'] != 'approved': continue
            if 'save_draft' in names: continue
            target = self.request['confirmed_alternative_time'] or self.request['requested_time']
            queries = [o for n,o in history if n == 'query_slots' and o.get('_material_id') == mid]
            if not queries: return 'query_slots', {'platform':self.request['platform'],'requested_time':target}, 'mock'
            slots = queries[-1]['data']
            if slots['available'] or any(d['material_id'] == mid for d in slots['existing_request_drafts']): return 'save_draft', {'material_id':mid,'proposed_time':target}, 'mock'
            if self.request['time_requirement'] == 'soft' and self.request['allow_alternative_suggestion'] and slots['alternatives']:
                return 'save_draft', {'material_id':mid,'proposed_time':slots['alternatives'][0]}, 'mock'
        return 'finish', {'decision_basis':'Deterministic mock policy finished from observed tool results'}, 'mock'
