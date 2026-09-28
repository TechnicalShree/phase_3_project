"""Durable entry points; run one server worker with this SQLite configuration."""
import sqlite3
from pathlib import Path
from threading import RLock

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Overwrite

from app.graph import build_graph
from app.guards import ingress


class Helpdesk:
    def __init__(self, directory='data'):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.directory / 'checkpoints.sqlite', check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.checkpointer = SqliteSaver(self.connection)
        self.graph = build_graph(self.checkpointer)
        # ponytail: serialize runs in one process; use Postgres + per-thread locks for multi-worker deployment.
        self.lock = RLock()

    def config(self, thread_id):
        return {'configurable': {'thread_id': thread_id, 'data_dir': str(self.directory)}, 'recursion_limit': 80}

    def prepare(self, text, thread_id):
        previous = self.graph.get_state(self.config(thread_id))
        if previous.next:
            raise ValueError('This thread has unfinished work; resolve it before sending a new message.')
        return {**ingress(text, bool(previous.values.get('history'))), 'egress_checked': False, 'messages': Overwrite([]), 'iterations': 0, 'fingerprints': [],
                'escalation': '', 'response': '', 'history': previous.values.get('history', [])}

    def run_ticket(self, text, thread_id):
        with self.lock:
            self.graph.invoke(self.prepare(text, thread_id), self.config(thread_id))
            return self.snapshot(thread_id)

    def stream_ticket(self, text, thread_id):
        with self.lock:
            for event in self.graph.stream(self.prepare(text, thread_id), self.config(thread_id), stream_mode='updates'):
                yield {'event': 'step', 'nodes': list(event)}
            yield {'event': 'result', **self.snapshot(thread_id)}

    def snapshot(self, thread_id):
        state = self.graph.get_state(self.config(thread_id))
        return {'thread_id': thread_id, 'values': state.values, 'next': list(state.next),
                'checkpoint_id': state.config['configurable'].get('checkpoint_id')}

    def close(self):
        self.connection.close()
