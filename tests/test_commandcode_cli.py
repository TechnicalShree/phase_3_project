import json
import os
import subprocess
import unittest
from unittest.mock import patch

from app.commandcode_cli import CommandCodeCLI
from app.graph import Triage, model
from app.tools import READ_TOOLS, create_ticket


class CLIAdapterChecks(unittest.TestCase):
    def test_validated_decisions_and_process_boundary(self):
        with patch.dict(os.environ, CMD_API_KEY='test-secret', CMD_CLI_PATH='/test/cmd',
                        LLM_PROVIDER='commandcode_cli'), patch('app.commandcode_cli.subprocess.run') as run:
            def output(value, code=0):
                run.return_value = subprocess.CompletedProcess([], code, json.dumps({
                    'type': 'result', 'subtype': 'success', 'finalText': json.dumps(value)}), '')
            output({'category': 'network', 'severity': 'low'})
            self.assertEqual(model().with_structured_output(Triage).invoke([('human', 'wifi')]).category, 'network')
            args, kwargs = run.call_args
            self.assertNotIn('test-secret', ' '.join(args[0]))
            self.assertNotIn('--yolo', args[0])
            self.assertIn('--no-session', args[0])
            self.assertEqual(kwargs['env']['COMMAND_CODE_API_KEY'], 'test-secret')
            self.assertEqual(kwargs['timeout'], 90)
            self.assertNotEqual(kwargs['cwd'], os.getcwd())
            output({'content': '', 'tool_calls': [{'name': 'lookup_campus_account', 'args': {'account_id': 'STU-1001'}}]})
            reply = model().bind_tools(READ_TOOLS).invoke([('human', 'lookup')])
            self.assertEqual(reply.tool_calls[0]['args'], {'account_id': 'STU-1001'})
            for invalid in [
                {'name': 'create_ticket', 'args': {}},
                {'name': 'lookup_campus_account', 'args': {'account_id': 123}},
                {'name': 'lookup_campus_account', 'args': {'account_id': 'STU-1001', 'approved': True}},
            ]:
                output({'content': '', 'tool_calls': [invalid]})
                with self.assertRaises(ValueError):
                    model().bind_tools(READ_TOOLS).invoke([('human', 'lookup')])
            output({'content': 'Done', 'tool_calls': []})
            with self.assertRaises(ValueError):
                model().bind_tools([create_ticket], tool_choice='create_ticket').invoke([('human', 'draft')])
            output({'category': 'invalid', 'severity': 'low'})
            with self.assertRaisesRegex(ValueError, 'invalid JSON'):
                model().with_structured_output(Triage).invoke([('human', 'wifi')])
            run.return_value.stdout = 'test-secret'
            with self.assertRaisesRegex(ValueError, 'invalid JSON'):
                model().invoke([('human', 'wifi')])
            output({}, code=4)
            with self.assertRaisesRegex(ValueError, 'exit 4'):
                model().invoke([('human', 'wifi')])
            run.side_effect = subprocess.TimeoutExpired('cmd', 90)
            with self.assertRaisesRegex(ValueError, 'timed out'):
                model().invoke([('human', 'wifi')])


if __name__ == '__main__':
    unittest.main()
