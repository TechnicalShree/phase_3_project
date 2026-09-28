import os
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage
from app.graph import MAX_ITERATIONS

os.environ['MODEL_MODE'] = 'demo'
from app.graph import build_graph


class ProjectChecks(unittest.TestCase):
    def test_categories(self):
        graph = build_graph()
        for text, category in [('reset password', 'account'), ('wifi issue', 'network'),
                               ('broken laptop', 'hardware'), ('help', 'general')]:
            self.assertEqual(graph.invoke({'text': text})['category'], category)


    def test_tools_are_called(self):
        result = build_graph().invoke({'text': 'wifi for STU-1001'})
        calls = [c['name'] for m in result['messages'] for c in getattr(m, 'tool_calls', [])]
        self.assertEqual(set(calls), {'search_knowledge_base', 'lookup_campus_account', 'check_service_status'})
        self.assertIn('North Hall', result['response'])

    def test_loop_circuit_breakers(self):
        for repeated, expected in [(True, 'duplicate_tool_call'), (False, 'iteration_limit')]:
            with patch('app.graph.model') as fake, patch.dict(os.environ, MODEL_MODE='live'):
                fake.return_value.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
                    'category': 'network', 'severity': 'low'}
                counter = iter(range(20))
                fake.return_value.bind_tools.return_value.invoke.side_effect = lambda _: AIMessage(
                    content='', tool_calls=[{'name': 'check_service_status',
                    'args': {'service': 'wifi' if repeated else str(next(counter))}, 'id': 'loop'}])
                result = build_graph().invoke({'text': 'wifi trouble'})
                self.assertEqual(result['escalation'], expected)
                self.assertLessEqual(result['iterations'], MAX_ITERATIONS)

    def test_real_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            script = "from app.service import Helpdesk; import sys,json; s=Helpdesk(sys.argv[1]); "
            first = script + "s.run_ticket('wifi problem', 'restart'); s.close()"
            subprocess.run([sys.executable, '-c', first, directory], check=True)
            second = script + "print(json.dumps(s.run_ticket('password reset', 'restart')['values']['history'])); s.close()"
            history = json.loads(subprocess.check_output([sys.executable, '-c', second, directory], text=True))
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['user'], 'wifi problem')


if __name__ == '__main__':
    unittest.main()
