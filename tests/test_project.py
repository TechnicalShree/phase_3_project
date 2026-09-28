import os
import unittest

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


if __name__ == '__main__':
    unittest.main()
