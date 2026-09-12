"""Offline preference evidence ledger; exports/merges always use a new directory."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import safe_store

VERSION = 'plan-a-v1'
EVENTS = Path('preferences/events')
SCOPES = ('work', 'personal', 'general')
KINDS = ('support', 'explicit', 'difference', 'exception', 'replace', 'decision', 'classify', 'promote')
# Fields that belong to the event schema. Anything else is dropped on write so the
# ledger never gains shapes that readers do not expect (see KNOWN_ISSUES D1).
EVENT_FIELDS = ('policy', 'preference_id', 'scope', 'module', 'text', 'source', 'evidence',
                'device', 'date', 'kind', 'confirmed_by', 'category', 'topic',
                'classification_state', 'choice', 'target', 'basis', 'penalty',
                'scope_target', 'category_target', 'task_id')

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def validate(e):
    # Legacy events have no component field and belong to S1 by storage contract.
    if isinstance(e, dict) and e.get('component', 's1') != 's1':
        raise ValueError('Preference scoring applies to S1 only')
    required = {'policy', 'preference_id', 'scope', 'module', 'text', 'source', 'evidence', 'device', 'date', 'kind'}
    if not isinstance(e, dict) or not required <= e.keys():
        missing=sorted(required-set(e)) if isinstance(e,dict) else sorted(required)
        raise ValueError('Expected one event object; missing fields: '+', '.join(missing))
    if any(not isinstance(e[k], str) or not e[k].strip() for k in required):
        raise ValueError('Event fields must be nonempty strings')
    if e['policy'] != VERSION:
        raise ValueError('Policy version mismatch; reconcile policies first')
    if e['scope'] not in SCOPES:
        raise ValueError('Invalid scope')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', e['preference_id']):
        raise ValueError('Invalid preference ID')
    if e['kind'] not in KINDS:
        raise ValueError('Invalid event kind')
    if e['kind']=='promote':
        if not isinstance(e.get('confirmed_by'),str) or not e['confirmed_by'].strip():
            raise ValueError('Promotion needs actual user confirmation evidence')
        if not isinstance(e.get('basis'),list) or not e['basis'] or any(not isinstance(k,str) or not re.fullmatch('[a-f0-9]{64}',k) for k in e['basis']):
            raise ValueError('Promotion needs reviewed evidence IDs in basis')
    confirmed_by = e.get('confirmed_by')
    if confirmed_by is not None and (not isinstance(confirmed_by, str) or not confirmed_by.strip()):
        raise ValueError('confirmed_by must be a nonempty string when present')
    for field in ('category', 'topic'):
        value = e.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f'{field} must be a nonempty string when present')
    state = e.get('classification_state')
    if state is not None and state not in ('staged', 'confirmed'):
        raise ValueError('classification_state must be staged or confirmed when present')
    if e['kind'] == 'decision':
        if e.get('choice') not in ('keep', 'exception', 'weaken', 'replace'):
            raise ValueError('Invalid decision choice')
        if not isinstance(e.get('target'), str) or not re.fullmatch('[a-f0-9]{64}', e['target']):
            raise ValueError('Decision needs a target event ID')
        if not isinstance(e.get('basis'), list) or any(not isinstance(x, str) or not re.fullmatch('[a-f0-9]{64}', x) for x in e['basis']):
            raise ValueError('Decision needs the reviewed evidence IDs')
        penalty = e.get('penalty')
        if penalty is not None and (e['choice'] != 'weaken' or type(penalty) is not int or penalty not in (1, 2)):
            raise ValueError('penalty only allowed for weaken decisions with value 1 or 2')
    if e['kind'] == 'classify':
        if not isinstance(e.get('target'), str) or not re.fullmatch('[a-f0-9]{64}', e['target']):
            raise ValueError('Classify needs a target event ID')
        if e.get('scope_target') not in SCOPES:
            raise ValueError('Classify needs a valid scope_target')
        if not isinstance(e.get('category_target'), str) or not e['category_target'].strip():
            raise ValueError('Classify needs a category_target')
        if e.get('classification_state') != 'confirmed':
            raise ValueError('Classify must set classification_state to confirmed')
        if confirmed_by is None:
            raise ValueError('Classify needs confirmed_by')
        if not isinstance(e.get('basis'), list) or any(not isinstance(x, str) or not re.fullmatch('[a-f0-9]{64}', x) for x in e['basis']):
            raise ValueError('Classify needs the reviewed evidence IDs')
    return e

def event_id(e):
    # Device and local timestamp do not distinguish duplicate observations.
    return digest([e['source'], e['preference_id'], e['scope'], e['kind']])

def normalize(e):
    """Return (clean_event, dropped_field_names).

    Redundant fields written by older callers (for example a stray ``component``)
    are dropped instead of stored, so readers can rely on the schema. Validation
    still runs first, so a genuinely wrong ``component`` value is still rejected
    rather than silently discarded.
    """
    if not isinstance(e, dict):
        return e, []
    dropped = sorted(k for k in e if k not in EVENT_FIELDS)
    return {k: v for k, v in e.items() if k in EVENT_FIELDS}, dropped

def canonical(e):
    clean, _ = normalize(e)
    return {k: v for k, v in clean.items() if k not in ('device', 'date')}

def load(root):
    events = {}
    policy_path = root / 'preferences/policy.json'
    if policy_path.exists():
        policy = json.loads(policy_path.read_text(encoding='utf-8'))
        if policy != {'version': VERSION, 'promotion': 10, 'difference_confirmation': 8, 'replacement_confirmation': 5}:
            raise ValueError('Policy configuration mismatch; reconcile before scoring')
    for p in sorted((root / EVENTS).glob('*.json')):
        safe_store.no_links(p)
        e = validate(json.loads(p.read_text(encoding='utf-8')))
        key = event_id(e)
        if p.stem != key:
            raise ValueError(f'Event filename mismatch: {p}')
        events[key] = e
    return events

def write_json(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    safe_store.atomic_bytes(p, safe_store.json_bytes(value))

def basis_valid(basis, ordinary):
    reviewed = set(basis)
    if not reviewed or not reviewed <= set(ordinary):
        return False
    if reviewed == set(ordinary):
        return True
    definitions = {(ordinary[k]['text'], ordinary[k]['module']) for k in reviewed}
    return len(definitions) == 1 and all(
        e['kind'] in ('support', 'explicit') and (e['text'], e['module']) in definitions
        for k, e in ordinary.items() if k not in reviewed)

def effective_preferences(snap):
    return [row for row in snap['preferences']
            if row['state'] == 'active' and not row['pending']
            and row['tier'] in ('user-explicit', 'long-term', 'high-tendency')]

def add_event(root, e):
    validate(e)
    e, _ = normalize(e)
    with safe_store.locked(root):
        existing = load(root)
        key = event_id(e)
        if key in existing and canonical(existing[key]) != canonical(e):
            raise ValueError('Same evidence ID differs; do not overwrite')
        if key not in existing:
            rel = (EVENTS / (key + '.json')).as_posix()
            safe_store.apply(root, {rel: safe_store.json_bytes(e)}, {rel: None}, already_locked=True)
        return key

def _classify_placements(events):
    """Evaluate classify events against their original (scope, preference_id) group.

    A classify applies only when its target is an existing support/explicit event,
    it is user-confirmed, and its basis still equals the original group's ordinary
    evidence. Conflicting placements (different scope/category for the same target)
    are not applied. Returns (applied, pending).
    """
    groups = {}
    for key, e in events.items():
        groups.setdefault((e['scope'], e['preference_id']), {})[key] = e
    candidates = {}
    pending = []
    for (scope, pref), group in groups.items():
        ordinary = {k: e for k, e in group.items() if e['kind'] not in ('decision', 'classify', 'promote')}
        for k, e in group.items():
            if e['kind'] != 'classify':
                continue
            target = e['target']
            if target not in ordinary or ordinary[target]['kind'] not in ('support', 'explicit'):
                pending.append({'event': k, 'target': target, 'reason': 'INVALID_CLASSIFY_TARGET'})
                continue
            if not e.get('confirmed_by') or e.get('classification_state') != 'confirmed':
                pending.append({'event': k, 'target': target, 'reason': 'CLASSIFY_UNCONFIRMED'})
                continue
            if not basis_valid(e.get('basis', []), ordinary):
                pending.append({'event': k, 'target': target, 'reason': 'CLASSIFY_BASIS_CHANGED'})
                continue
            candidates.setdefault(target, []).append((k, e))
    applied = {}
    for target, items in candidates.items():
        if len({(e['scope_target'], e['category_target']) for _, e in items}) != 1:
            for k, e in items:
                pending.append({'event': k, 'target': target, 'reason': 'CLASSIFY_CONFLICT'})
            continue
        key, chosen = items[0]
        applied[target] = {'event': key, 'scope_target': chosen['scope_target'],
                           'category_target': chosen['category_target'],
                           'confirmed_by': chosen['confirmed_by']}
    return applied, pending


def snapshot(events):
    """Build preference rows by effective scope.

    Real classification scoring: a support/explicit event with a valid confirmed
    classify event is projected into the classify target scope and scores there.
    Events marked staged without a valid classify stay in the staged list and do
    not score in any core preference row. Historical event files are never
    rewritten; projection is computed at snapshot time.
    """
    applied, classify_pending = _classify_placements(events)
    eff_scope = {}
    staged_by_key = {}
    staged = []
    for key, e in sorted(events.items()):
        if e['kind'] in ('decision', 'classify', 'promote'):
            continue
        move = applied.get(key)
        if move:
            eff_scope[key] = (move['scope_target'], e['preference_id'])
            continue
        if e.get('classification_state') == 'staged':
            entry = {'event': key, 'scope': e['scope'], 'preference_id': e['preference_id'],
                     'module': e.get('module'), 'category': e.get('category'), 'topic': e.get('topic'),
                     'text': e['text'], 'source': e['source'], 'evidence': e['evidence'], 'pending': []}
            if e['kind'] == 'explicit' and not e.get('confirmed_by'):
                entry['pending'].append({'reason': 'EXPLICIT_UNCONFIRMED'})
            staged.append(entry)
            staged_by_key[key] = entry
            continue
        eff_scope[key] = (e['scope'], e['preference_id'])
    classify_events = {key: e for key, e in events.items() if e['kind'] == 'classify'}
    for item in classify_pending:
        target_entry = staged_by_key.get(item['target'])
        if target_entry is None:
            ce = classify_events.get(item['event'])
            if ce is not None:
                # 无效/悬空 target：把待复核信息归到同组 staged 条目，避免静默丢失。
                target_entry = next((entry for entry in staged
                                     if entry['scope'] == ce['scope']
                                     and entry['preference_id'] == ce['preference_id']), None)
        if target_entry is not None:
            target_entry['pending'].append({'event': item['event'], 'reason': item['reason']})
    groups = {}
    for key, e in events.items():
        if e['kind'] in ('decision','promote'):
            groups.setdefault((e['scope'], e['preference_id']), {})[key] = e
        elif key in eff_scope:
            groups.setdefault(eff_scope[key], {})[key] = e
    rows = []
    for (scope, pref), group in sorted(groups.items()):
        ordinary = {k: e for k, e in group.items() if e['kind'] not in ('decision','promote')}
        definitions = {(e['text'], e['module']) for e in ordinary.values()}
        pending = []
        if len(definitions) != 1:
            pending.append({'reason': 'DEFINITION_CONFLICT'})
        decisions = {}
        stale = []
        for k, e in group.items():
            if e['kind'] != 'decision':
                continue
            if not e.get('confirmed_by'):
                pending.append({'event': k, 'reason': 'DECISION_UNCONFIRMED'})
                continue
            target = e['target']
            if target not in ordinary or ordinary[target]['kind'] not in ('difference', 'exception', 'replace'):
                pending.append({'event': k, 'reason': 'INVALID_DECISION_TARGET'})
                continue
            # Missing evidence or evidence not reviewed on another client requires review.
            if not basis_valid(e['basis'], ordinary):
                stale.append({'event': k, 'target': target, 'reason': 'DECISION_BASIS_CHANGED'})
                continue
            decisions.setdefault(target, []).append({'choice': e['choice'], 'penalty': e.get('penalty', 2), 'basis': sorted(e['basis'])})
        accepted = {}
        for target, choices in decisions.items():
            # A re-confirmation over a strictly larger evidence set supersedes its old review.
            choices = [c for c in choices if not any(set(c['basis']) < set(other['basis']) for other in choices)]
            if len({(c['choice'], c['penalty']) for c in choices}) != 1:
                pending.append({'event': target, 'reason': 'DECISION_CONFLICT'})
            else:
                chosen = min(choices, key=lambda x: json.dumps(x, sort_keys=True))
                if chosen['choice'] == 'weaken' and chosen['penalty'] == 1:
                    mature = len({e['source'] for e in ordinary.values() if e['kind'] in ('support', 'explicit')}) >= 10
                    mature &= any(e['kind'] == 'explicit' and e.get('confirmed_by') for e in ordinary.values())
                    repeated = len({e['source'] for e in ordinary.values() if e['kind'] == 'difference'}) >= 2
                    if not mature or not repeated or len(definitions) != 1:
                        pending.append({'event': target, 'reason': 'INVALID_MILD_PENALTY'})
                        continue
                accepted[target] = chosen
        pending.extend(item for item in stale if item['target'] not in accepted)
        for item in classify_pending:
            if item['target'] in ordinary:
                pending.append({'event': item['event'], 'reason': item['reason']})
        classifications = []
        for target_key in ordinary:
            move = applied.get(target_key)
            if move:
                classifications.append({'event': move['event'], 'target': target_key,
                                        'scope_target': move['scope_target'],
                                        'category_target': move['category_target'],
                                        'confirmed_by': move['confirmed_by']})
        supports = {e['source'] for e in ordinary.values() if e['kind'] in ('support', 'explicit')}
        explicit_confirmed = any(e['kind'] == 'explicit' and bool(e.get('confirmed_by')) for e in ordinary.values())
        if any(e['kind'] == 'explicit' and not e.get('confirmed_by') for e in ordinary.values()):
            pending.append({'reason': 'EXPLICIT_UNCONFIRMED'})
        # Count all unique support evidence; penalties stay explicit and auditable.
        score = min(10, max(0, len(supports) - sum(c['penalty'] for c in accepted.values() if c['choice'] == 'weaken')))
        retired = False
        for key, e in ordinary.items():
            kind = e['kind']
            if kind not in ('difference', 'exception', 'replace'):
                continue
            if key in accepted:
                retired |= accepted[key]['choice'] == 'replace'
                continue
            threshold = 5 if kind == 'replace' else 8
            if score >= threshold:
                pending.append({'event': key, 'reason': 'CONFIRM_REPLACEMENT' if kind == 'replace' else 'CONFIRM_DIFFERENCE'})
            elif kind == 'replace':
                retired = True
            elif kind == 'difference':
                pending.append({'event': key, 'reason': 'UNRESOLVED_DIFFERENCE'})
        tier = 'promotion-pending' if score == 10 else 'high-tendency' if score >= 8 else 'tendency' if score >= 4 else 'candidate'
        promotions=[k for k,e in group.items() if e['kind']=='promote'
                    and e.get('confirmed_by') and basis_valid(e.get('basis',[]),ordinary)
                    and (e['text'],e['module']) in definitions]
        if score>=10 and promotions and not pending and not retired:
            tier='long-term'
        if explicit_confirmed:
            tier = 'user-explicit'
        if score >= 10 and not explicit_confirmed and not retired and tier!='long-term':
            pending.append({'reason': 'CONFIRM_PROMOTION'})
        rows.append({'preference_id': pref, 'scope': scope, 'definitions': sorted(definitions),
                     'support_count': len(supports), 'score': score, 'tier': tier,
                     'state': 'retired' if retired else 'review-required' if pending else 'active',
                     'pending': pending, 'basis': sorted(ordinary), 'classifications': classifications,
                     'promotion_evidence':promotions,
                     'decisions': {k: v for k, v in accepted.items()},
                     'independent_tasks': len({e.get('task_id', e['source'].split(':')[0]) for e in ordinary.values() if e['kind'] in ('support', 'explicit')})})
    rows_by = {(r['scope'], r['preference_id']): r for r in rows}
    topic_keys = {}
    for key, e in events.items():
        if e['kind'] in ('decision', 'classify', 'promote'):
            continue
        topic = e.get('topic')
        if not topic:
            continue
        pair = eff_scope.get(key)
        if pair is None:
            continue
        topic_keys.setdefault(topic, [])
        if pair not in topic_keys[topic]:
            topic_keys[topic].append(pair)
    cross_domain = []
    for topic in sorted(topic_keys):
        pairs = sorted(topic_keys[topic])
        if len({scope for scope, _ in pairs}) < 2:
            continue
        entries = []
        for pair in pairs:
            r = rows_by.get(pair)
            if not r:
                continue
            entries.append({'scope': pair[0], 'preference_id': pair[1],
                            'definition': r['definitions'][0] if r['definitions'] else '',
                            'score': r['score'], 'tier': r['tier'], 'state': r['state']})
        cross_domain.append({'topic': topic, 'entries': entries})
    return {'policy': VERSION, 'knowledge': 'local-known-only', 'preferences': rows,
            'staged': staged, 'cross_domain': cross_domain}
