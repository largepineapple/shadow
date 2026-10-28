import json
from .llm_client import SYSTEM, TOOL_PARAMETERS
from .time_utils import display_time


class Agent:
    def __init__(self, tools, client, trace, max_steps=8, max_tool_calls=10):
        self.tools, self.client, self.trace = tools, client, trace
        self.max_steps, self.max_calls = max_steps, max_tool_calls
        self.history = []
        self.slot_observations = {}

    def run(self):
        messages = [{'role':'system','content':SYSTEM}, {'role':'user','content':json.dumps(self.tools.request)}]
        calls = 0
        invalid = 0
        for step in range(self.max_steps):
            try:
                name, args, call_id = self.client.choose(messages)
                if name not in TOOL_PARAMETERS or not isinstance(args, dict): raise ValueError('Invalid model action')
                props = TOOL_PARAMETERS[name]
                required = set(props) - ({'candidate_count'} if name == 'query_slots' else set())
                if not required <= set(args) or set(args) - set(props): raise ValueError('Invalid action arguments')
                for key, value in args.items():
                    expected = int if props[key]['type'] == 'integer' else str
                    if type(value) is not expected: raise ValueError('Invalid argument type')
            except Exception as exc:
                invalid += 1
                self.trace.add('model_error', {}, {'error':str(exc)})
                if invalid >= 2: return self.result('incomplete', 'Model request/response failed: '+str(exc))
                messages.append({'role':'user','content':'Previous response invalid or unavailable. Return one valid tool call.'})
                continue
            if name == 'finish':
                self.trace.add(name, args, {'ok':True}, args['decision_basis'])
                return self.result()
            if calls >= self.max_calls:
                return self.result('incomplete', 'max_tool_calls limit reached')
            observation = self.tools.execute(name, args)
            calls += 1
            # Attribution comes from actual arguments/context, not from model output claims.
            mid = args.get('material_id')
            if name == 'query_slots':
                reviewed = [a['material_id'] for n,a,o in self.history if n == 'check_rules']
                mid = reviewed[-1] if reviewed else None
                if mid and observation['ok']:
                    self.slot_observations[mid] = observation['data']
            self.history.append((name,args,observation))
            self.trace.add(name,args,observation)
            feedback = dict(observation, _material_id=mid)
            messages.append({'role':'assistant','content':None,'tool_calls':[{'id':call_id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]})
            messages.append({'role':'tool','tool_call_id':call_id,'name':name,'content':json.dumps(feedback)})
        return self.result('incomplete', 'max_steps limit reached')

    def result(self, forced=None, reason=None):
        r = self.tools.request
        items, states = [], []
        for mid in r['material_ids']:
            item = dict(material_id=mid,review_status='insufficient_data',risk_reasons=[],requested_time=display_time(r['requested_time'],r['timezone']),suggested_time=None,confirmation_items=[],draft_status='not_saved',draft_id=None)
            reviews = [o for n,a,o in self.history if n=='check_rules' and a.get('material_id')==mid and o['ok']]
            saves = [o for n,a,o in self.history if n=='save_draft' and a.get('material_id')==mid]
            if reviews:
                item.update({k:reviews[-1]['data'][k] for k in ('review_status','risk_reasons')})
            review = item['review_status']
            state = 'incomplete'
            if review == 'insufficient_data':
                state = 'needs_information' if reviews else 'incomplete'
                item['confirmation_items'] = ['Supplement missing fields: '+','.join(reviews[-1]['data']['missing_fields'])] if reviews else []
            elif review in ('blocked','review_required'):
                state = 'blocked' if review == 'blocked' else 'needs_confirmation'
                if review == 'review_required': item['confirmation_items']=['Human risk review required']
            elif saves and saves[-1]['ok']:
                item.update({k:saves[-1]['data'][k] for k in ('draft_status','draft_id')})
                item['suggested_time'] = saves[-1]['data']['proposed_time']
                state = 'completed'
            elif saves:
                error = saves[-1]['error']
                state = 'save_failed'
                item['draft_status']='failed'
                item['confirmation_items']=[error['code']+': '+error['message']]
            else:
                queries = [self.slot_observations[mid]] if mid in self.slot_observations else []
                if queries and not queries[-1]['available']:
                    state = 'needs_confirmation'
                    if r['allow_alternative_suggestion'] and queries[-1]['alternatives']:
                        item['suggested_time']=queries[-1]['alternatives'][0]
                    item['confirmation_items']=['Requested slot occupied; explicit user choice/confirmation required']
            if item['suggested_time'] and item['suggested_time'] != item['requested_time']:
                item['time_change_reason']='Original slot occupied or external alternative explicitly confirmed'
            item['outcome_status'] = state
            items.append(item)
            states.append(state)
        priority = ['incomplete','save_failed','blocked','needs_information','needs_confirmation','completed']
        status = forced or next(s for s in priority if s in states)
        return {'request_id':r['request_id'],'status':status,'materials':items,'published':False,'reason':reason or ('Local draft operation completed; nothing published' if status=='completed' else 'See material outcomes; no publication performed')}
