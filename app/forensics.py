"""Immutable checkpoint timeline and constrained, approval-safe replay."""
from app.graph import MAX_ITERATIONS, MAX_DELEGATIONS
from app.guards import redact

CATEGORIES = {'account', 'network', 'hardware', 'general'}


def anomalies(snapshot):
    state = snapshot.values
    flags = []
    if state.get('category') and state['category'] not in CATEGORIES:
        flags.append('invalid_category')
    if state.get('iterations', 0) >= MAX_ITERATIONS:
        flags.append('iteration_limit_reached')
    if state.get('delegations', 0) >= MAX_DELEGATIONS:
        flags.append('delegation_limit_reached')
    if state.get('escalation'):
        flags.append(state['escalation'])
    if not snapshot.next and state.get('text'):
        if not state.get('response', '').strip():
            flags.append('empty_final_response')
        if not state.get('egress_checked'):
            flags.append('missing_egress_check')
    if state.get('response') != redact(state.get('response', '')) and state.get('egress_checked'):
        flags.append('pii_after_egress')
    if (state.get('write_result') or {}).get('status') == 'created':
        if state.get('severity') != 'high' or state.get('blocked'):
            flags.append('write_policy_violation')
    return list(dict.fromkeys(flags))


def state_forensics(graph, config):
    snapshots = list(graph.get_state_history(config))
    return [{
        'checkpoint_id': item.config['configurable']['checkpoint_id'],
        'parent_id': item.parent_config['configurable'].get('checkpoint_id') if item.parent_config else None,
        'created_at': item.created_at, 'step': (item.metadata or {}).get('step'),
        'source': (item.metadata or {}).get('source'), 'next': list(item.next),
        'category': item.values.get('category'), 'severity': item.values.get('severity'),
        'iterations': item.values.get('iterations', 0), 'delegations': item.values.get('delegations', 0),
        'response': redact(item.values.get('response', ''))[:400],
        'flags': anomalies(item), 'branch_from': item.values.get('branch_from'),
    } for item in reversed(snapshots)]


def find_bad_checkpoint(graph, config):
    snapshots = list(graph.get_state_history(config))
    by_id = {item.config['configurable']['checkpoint_id']: item for item in snapshots}
    for item in snapshots:
        flags = anomalies(item)
        if not flags:
            continue
        # Find where the anomaly first appeared on this lineage, not an inherited bad value.
        while item.parent_config:
            parent = by_id.get(item.parent_config['configurable'].get('checkpoint_id'))
            if parent is None or flags[0] not in anomalies(parent):
                break
            item = parent
        return {'checkpoint_id': item.config['configurable']['checkpoint_id'], 'flags': anomalies(item),
                'parent_config': item.parent_config}
    return None
