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


if __name__ == '__main__':
    unittest.main()
