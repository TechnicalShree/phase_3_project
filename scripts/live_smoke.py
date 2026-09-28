"""Opt-in OpenRouter check; uses credits and fictional data, never the app's saved threads."""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['MODEL_MODE'] = 'live'
from app.service import Helpdesk

if not os.getenv('OPENROUTER_API_KEY'):
    raise SystemExit('Add OPENROUTER_API_KEY to .env before running this opt-in check.')

with tempfile.TemporaryDirectory() as directory:
    service = Helpdesk(directory)
    try:
        result = service.run_ticket('Campus wifi issue for STU-1001. Look up this account and check the wifi service status.', 'live-read')
        values = service.graph.get_state(service.config('live-read')).values
        calls = [call['name'] for message in values['messages'] for call in getattr(message, 'tool_calls', [])]
        assert calls, 'Live model did not call a lookup tool'
        assert len(values['findings']) >= 3, 'Live supervisor did not dispatch the specialists'
        assert result['values']['response'], 'No final answer'
        pending = service.run_ticket('Delete campus account STU-1002: the student has withdrawn. Request administrator review.', 'live-write')
        assert pending['pending'], 'High-severity action did not pause for approval'
        assert not service.tickets(), 'A ticket was written before approval'
        denied = service.resume('live-write', 'deny', pending['checkpoint_id'])
        assert denied['values']['write_result']['status'] == 'denied'
        assert not service.tickets(), 'Denial created a record'
        print('PASS: OpenRouter classification, bound tools, supervisor, specialists, draft, interrupt and denial.')
        print('Lookup tools observed:', ', '.join(sorted(set(calls))))
    finally:
        service.close()
