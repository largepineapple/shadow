import json
from datetime import timedelta
from pathlib import Path
from .storage import digest
from .time_utils import parse_time, display_time, overlaps
from .policy import authorized


def ok(data):
    return {'ok': True, 'data': data, 'error': None}


def fail(code, message):
    return {'ok': False, 'data': None, 'error': {'code': code, 'message': message}}


class Tools:
    def __init__(self, request, storage, data_dir=None, inject_failure=False):
        self.request, self.storage, self.inject_failure = request, storage, inject_failure
        root = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / 'data'
        self.materials = {m['id']: m for m in json.loads((root / 'materials.json').read_text(encoding='utf-8-sig'))}
        self.rules = json.loads((root / 'rules.json').read_text(encoding='utf-8-sig'))
        self.schedule = json.loads((root / 'schedule.json').read_text(encoding='utf-8-sig'))

    def get_material(self, material_id):
        return ok(self.materials[material_id]) if material_id in self.materials else fail('NOT_FOUND', material_id)

    def check_rules(self, material_id):
        m = self.materials.get(material_id)
        missing = [f for f in self.rules['required_fields'] if not m or m.get(f) is None or m.get(f) == '']
        reasons = []
        status = 'approved'
        if missing:
            status = 'insufficient_data'
            reasons.append({'rule_id': self.rules['missing_rule'], 'reason': 'Missing required metadata', 'fields': missing})
        if m and m.get('sensitive_flags'):
            status = 'review_required' if not missing else status
            reasons.append({'rule_id': self.rules['sensitive_rule']['id'], 'reason': 'Sensitive content requires human review'})
        if m and m.get('copyright_status') == self.rules['copyright_rule']['blocked_value']:
            status = 'blocked'
            reasons.append({'rule_id': self.rules['copyright_rule']['id'], 'reason': 'Copyright prohibits scheduling'})
        return ok({'review_status': status, 'risk_reasons': reasons, 'missing_fields': missing})

    def conflicts(self, platform, start, exclude_id=None):
        begin = parse_time(start)
        end = begin + timedelta(minutes=self.rules['slot_minutes'])
        occupied = [x for x in self.schedule if x['status'] in ('occupied', 'confirmed', 'published', 'scheduled')]
        occupied += self.storage.drafts()
        return [x for x in occupied if x['platform'] == platform and (exclude_id is None or x.get('id') != exclude_id) and overlaps(begin, end, parse_time(x['start']), parse_time(x['end']))]

    def query_slots(self, platform, requested_time, candidate_count=3):
        if platform != self.request['platform'] or type(candidate_count) is not int or not 1 <= candidate_count <= 10:
            return fail('INVALID_ARGUMENT', 'Invalid platform or candidate_count')
        start = parse_time(requested_time)
        alternatives = []
        for step in range(1, 49):
            candidate = display_time((start + timedelta(minutes=step*self.rules['candidate_step_minutes'])).isoformat(), self.request['timezone'])
            if not self.conflicts(platform, candidate):
                alternatives.append(candidate)
            if len(alternatives) >= candidate_count:
                break
        return ok({'requested_time': display_time(requested_time, self.request['timezone']), 'available': not bool(self.conflicts(platform, requested_time)), 'alternatives': alternatives, 'existing_request_drafts': [d for d in self.storage.drafts() if d['request_id'] == self.request['request_id']]})

    def save_draft(self, material_id, proposed_time):
        r = self.request
        if material_id not in r['material_ids']:
            return fail('INVALID_ARGUMENT', 'Material outside request')
        review = self.check_rules(material_id)['data']
        if review['review_status'] != 'approved':
            return fail('REVIEW_NOT_APPROVED', review['review_status'])
        if not authorized(r, proposed_time):
            return fail('CONFIRMATION_REQUIRED', 'Hard time change requires external user confirmation')
        proposed_time = display_time(proposed_time, r['timezone'])
        normalized = dict(r)
        for field in ('requested_time', 'confirmed_alternative_time'):
            if normalized[field]: normalized[field] = parse_time(normalized[field]).isoformat()
        normalized['material_ids'] = sorted(normalized['material_ids'])
        fingerprint = digest(normalized)
        key = digest([r['request_id'], material_id, r['platform'], parse_time(r['requested_time']).isoformat(), parse_time(proposed_time).isoformat()])
        try:
            with self.storage.transaction() as db:
                old = db.execute('SELECT fingerprint FROM requests WHERE id=?', (r['request_id'],)).fetchone()
                if old and old['fingerprint'] != fingerprint:
                    return fail('REQUEST_CONTENT_CONFLICT', 'request_id already has different content; use a new request_id for confirmation')
                existing = db.execute('SELECT id FROM drafts WHERE idempotency_key=?', (key,)).fetchone()
                if existing:
                    return ok({'draft_status': 'existing', 'draft_id': existing['id'], 'proposed_time': proposed_time})
                if self.conflicts(r['platform'], proposed_time):
                    return fail('SLOT_CONFLICT', 'Slot is occupied')
                if self.inject_failure:
                    return fail('SAVE_UNAVAILABLE', 'Injected storage failure')
                db.execute('INSERT OR IGNORE INTO requests VALUES (?,?)', (r['request_id'], fingerprint))
                end = (parse_time(proposed_time) + timedelta(minutes=self.rules['slot_minutes'])).isoformat()
                cur = db.execute('INSERT INTO drafts(idempotency_key,request_id,material_id,platform,start,end) VALUES (?,?,?,?,?,?)', (key,r['request_id'],material_id,r['platform'],proposed_time,end))
                return ok({'draft_status': 'saved', 'draft_id': cur.lastrowid, 'proposed_time': proposed_time})
        except Exception as exc:
            return fail('SAVE_UNAVAILABLE', str(exc))

    def execute(self, name, arguments):
        if name not in ('get_material','check_rules','query_slots','save_draft') or not isinstance(arguments, dict):
            return fail('INVALID_TOOL', 'Unknown tool or invalid arguments')
        if 'material_id' in arguments and arguments['material_id'] not in self.request['material_ids']:
            return fail('INVALID_ARGUMENT', 'Material outside request')
        try:
            return getattr(self, name)(**arguments)
        except Exception as exc:
            return fail('TOOL_ERROR', str(exc))
