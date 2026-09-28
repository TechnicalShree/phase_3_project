"""Durable entry points; run one server worker with this SQLite configuration."""
import sqlite3
import os
from pathlib import Path
from threading import Lock

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Overwrite, Command

from app.graph import build_graph
from app.guards import ingress, egress, redact
from app.tools import clean_draft, ticket_db
import json
from app.forensics import state_forensics, find_bad_checkpoint, CATEGORIES


class Helpdesk:
    def __init__(self, directory='data'):
        if os.getenv('MODEL_MODE', 'demo') not in ('demo', 'live'):
            raise ValueError('MODEL_MODE must be demo or live.')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.directory / 'checkpoints.sqlite', check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.checkpointer = SqliteSaver(self.connection)
        self.graph = build_graph(self.checkpointer)
        # ponytail: serialize runs in one process; use Postgres + per-thread locks for multi-worker deployment.
        self.lock = Lock()

    def config(self, thread_id):
        return {'configurable': {'thread_id': thread_id, 'checkpoint_ns': '', 'data_dir': str(self.directory)}, 'recursion_limit': 80}

    def prepare(self, text, thread_id):
        previous = self.graph.get_state(self.config(thread_id))
        if previous.next:
            raise ValueError('This thread has unfinished work; resolve it before sending a new message.')
        return {**ingress(text, bool(previous.values.get('history'))), 'egress_checked': False, 'messages': Overwrite([]), 'iterations': 0, 'fingerprints': [],
                'escalation': '', 'response': '', 'research_done': False, 'specialist_done': False,
                'draft': None, 'write_result': None, 'delegations': 0, 'routing': [], 'findings': Overwrite([]), 'history': previous.values.get('history', [])}

    def run_ticket(self, text, thread_id):
        with self.lock:
            self.graph.invoke(self.prepare(text, thread_id), self.config(thread_id))
            return self.snapshot(thread_id)

    def stream_ticket(self, text, thread_id):
        with self.lock:
            for namespace, event in self.graph.stream(self.prepare(text, thread_id), self.config(thread_id),
                                                       stream_mode='updates', subgraphs=True):
                yield {'event': 'step', 'nodes': list(event), 'namespace': list(namespace)}
            yield {'event': 'result', **self.snapshot(thread_id)}

    def snapshot(self, thread_id):
        state = self.graph.get_state(self.config(thread_id))
        values = dict(state.values)
        if values:
            values['response'] = egress(values)['response']
            values['messages'] = [{'type': m.type, 'content': redact(str(m.content))} for m in values.get('messages', [])]
            values['findings'] = [{**f, 'advice': redact(f['advice'])} for f in values.get('findings', [])]
        pending = [{'id': item.id, **item.value} for task in state.tasks for item in task.interrupts]
        return {'thread_id': thread_id, 'values': values, 'next': list(state.next), 'pending': pending,
                'checkpoint_id': state.config['configurable'].get('checkpoint_id') if state.config else None}

    def resume(self, thread_id, decision, checkpoint_id, draft=None):
        with self.lock:
            state = self.graph.get_state(self.config(thread_id))
            interrupts = [i for task in state.tasks for i in task.interrupts]
            current_id = state.config['configurable'].get('checkpoint_id') if state.config else None
            if not interrupts or current_id != checkpoint_id:
                raise ValueError('Approval is missing or stale. Reload this thread before reviewing.')
            if decision not in ('approve', 'deny', 'edit'):
                raise ValueError('Unknown review decision.')
            payload = {'decision': decision}
            if decision == 'edit':
                payload['draft'] = clean_draft(draft)
            self.graph.invoke(Command(resume={interrupts[0].id: payload}), self.config(thread_id))
            return self.snapshot(thread_id)

    def threads(self):
        # SQLite's checkpointer already indexes thread IDs; no duplicate conversation registry.
        with self.lock:
            self.checkpointer.setup()
            ids = self.connection.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns='' ORDER BY thread_id").fetchall()
            return [self.snapshot(row[0]) for row in ids]

    def tickets(self):
        db = ticket_db(self.directory)
        try:
            return [{'ticket_id': f'IT-{row[0]:05d}', 'thread_id': row[1], 'draft': json.loads(row[2]),
                     'decision': row[3], 'created_at': row[4]} for row in db.execute(
                         'SELECT id,thread_id,payload,decision,created_at FROM tickets ORDER BY id DESC')]
        finally:
            db.close()

    def forensics(self, thread_id):
        with self.lock:
            return {'thread_id': thread_id, 'timeline': state_forensics(self.graph, self.config(thread_id)),
                    'bad_checkpoint': find_bad_checkpoint(self.graph, self.config(thread_id))}

    def checkpoint(self, thread_id, checkpoint_id):
        config = self.config(thread_id)
        config['configurable']['checkpoint_id'] = checkpoint_id
        state = self.graph.get_state(config)
        if not state.values or not state.values.get('category'):
            raise ValueError('Choose a checkpoint after classification in this thread.')
        return state

    def apply_correction(self, thread_id, checkpoint_id, category):
        if category not in CATEGORIES:
            raise ValueError('Correction must be a supported campus category.')
        source = self.checkpoint(thread_id, checkpoint_id)
        # Never accept arbitrary state updates (especially approval/write fields) from the API.
        return self.graph.update_state(source.config, {
            'category': category, 'branch_from': checkpoint_id, 'draft': None, 'write_result': None,
            'messages': Overwrite([]), 'findings': Overwrite([]), 'fingerprints': [], 'iterations': 0,
            'delegations': 0, 'routing': [], 'research_done': False, 'specialist_done': False,
            'response': '', 'egress_checked': False, 'escalation': '',
        }, as_node='triage')

    def time_travel(self, thread_id, checkpoint_id, category):
        with self.lock:
            source = self.checkpoint(thread_id, checkpoint_id)
            if source.values.get('blocked'):
                raise ValueError('Blocked requests cannot be replayed past ingress.')
            branch = self.apply_correction(thread_id, checkpoint_id, category)
            self.graph.invoke(None, branch)
            result = self.snapshot(thread_id)
            result['source_checkpoint_id'] = checkpoint_id
            return result

    def demo_fault(self, thread_id):
        with self.lock:
            if self.graph.get_state(self.config(thread_id)).values:
                raise ValueError('Use a new thread ID for the controlled fault demo.')
            self.graph.invoke(self.prepare('Campus wifi outage in North Hall affecting all students', thread_id), self.config(thread_id))
            checkpoints = list(self.graph.get_state_history(self.config(thread_id)))
            source = next(s for s in reversed(checkpoints) if s.values.get('category') and s.next == ('supervisor',))
            self.graph.update_state(source.config, {'category': 'invalid_demo'}, as_node='triage')
            result = {'state': self.snapshot(thread_id),
                      'timeline': state_forensics(self.graph, self.config(thread_id)),
                      'bad_checkpoint': find_bad_checkpoint(self.graph, self.config(thread_id)), 'thread_id': thread_id}
            return result

    def close(self):
        self.connection.close()
