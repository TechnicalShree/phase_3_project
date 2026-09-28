"""Go-plan headless adapter: validated JSON decisions, not native API tool calling."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4

from langchain_core.messages import AIMessage, convert_to_messages
from pydantic import BaseModel, ConfigDict, Field


class ToolDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str
    args: dict


class Reply(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    content: str
    tool_calls: list[ToolDecision] = Field(max_length=3)


class CommandCodeCLI:
    def __init__(self, schema=None, tools=(), tool_choice=None):
        self.schema, self.tools, self.tool_choice = schema, tools, tool_choice
        local = Path(__file__).resolve().parents[1] / '.venv/commandcode/node_modules/.bin/cmd'
        self.executable = os.getenv('CMD_CLI_PATH') or (str(local) if local.exists() else shutil.which('command-code'))
        if not self.executable:
            raise ValueError('Install Command Code CLI or set CMD_CLI_PATH to its executable.')
        if not os.getenv('CMD_API_KEY'):
            raise ValueError('Command Code CLI requires CMD_API_KEY in .env.')

    def with_structured_output(self, schema, method='function_calling'):
        return CommandCodeCLI(schema=schema)

    def bind_tools(self, tools, tool_choice=None):
        return CommandCodeCLI(tools=tools, tool_choice=tool_choice)

    def invoke(self, messages):
        schema = self.schema or Reply
        conversation = [message.model_dump(include={'type', 'content', 'tool_calls', 'tool_call_id', 'name'})
                        for message in convert_to_messages(messages)]
        tool_schemas = [{'name': tool.name, 'description': tool.description,
                         'parameters': tool.tool_call_schema.model_json_schema()} for tool in self.tools]
        prompt = ('Return ONLY one JSON object matching the output_schema, without markdown. '
                  'Act as the assistant in the supplied conversation, obeying its system messages. '
                  'Do not use CLI tools. Tool requests are JSON data for the outer application. '
                  'If tools are supplied, request needed lookups before answering; after their results '
                  'arrive, give advice with tool_calls=[]. Never invent lookup results.\n' +
                  json.dumps({'output_schema': schema.model_json_schema(), 'tools': tool_schemas,
                              'required_tool': self.tool_choice, 'conversation': conversation}))
        # ponytail: one process per decision; replace with a native API provider if throughput matters.
        with tempfile.TemporaryDirectory(prefix='campus-model-') as directory:
            try:
                result = subprocess.run([
                    self.executable, '-p', '--model', os.getenv('CMD_MODEL', 'stealth/space-bunny-alpha'),
                    '--output-format', 'json', '--max-turns', '2', '--skip-onboarding',
                    '--no-session', '--no-skills', '--no-auto-update', '--permission-mode', 'dont-ask',
                    '--mod', str(Path(__file__).with_name('commandcode_json.mjs')),
                ], input=prompt, text=True, capture_output=True, cwd=directory,
                    env={**os.environ, 'COMMAND_CODE_API_KEY': os.environ['CMD_API_KEY']}, timeout=90)
            except subprocess.TimeoutExpired:
                raise ValueError('Command Code CLI timed out after 90 seconds.') from None
        # Never forward raw stdout/stderr: provider errors may contain credentials or prompt data.
        if result.returncode:
            raise ValueError(f'Command Code CLI failed (exit {result.returncode}); check plan/model availability.')
        try:
            frames = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            if any(frame.get('event', {}).get('type') in ('mod_error', 'tool_running') for frame in frames):
                raise ValueError('Unexpected CLI tool activity or mod failure.')
            final = frames[-1]
            if final.get('type') != 'result' or final.get('subtype') != 'success':
                raise ValueError('Missing successful CLI result.')
            reply = schema.model_validate_json(final['finalText'])
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError('Command Code CLI returned an invalid JSON decision; no action executed.') from None
        if self.schema:
            return reply
        allowed = {tool.name: tool for tool in self.tools}
        if self.tool_choice and (len(reply.tool_calls) != 1 or reply.tool_calls[0].name != self.tool_choice):
            raise ValueError('Command Code CLI did not return the required tool draft.')
        calls = []
        for call in reply.tool_calls:
            if call.name not in allowed:
                raise ValueError('Command Code CLI requested an unavailable tool.')
            arg_schema = allowed[call.name].tool_call_schema
            if set(call.args) - set(arg_schema.model_fields):
                raise ValueError('Command Code CLI supplied unknown tool arguments.')
            try:
                args = arg_schema.model_validate(call.args, strict=True).model_dump()
            except ValueError:
                raise ValueError('Command Code CLI supplied invalid tool arguments.') from None
            calls.append({'name': call.name, 'args': args, 'id': str(uuid4())})
        return AIMessage(content=reply.content, tool_calls=calls)
