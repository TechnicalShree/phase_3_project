"""Campus IT graph. MODEL_MODE=demo is an explicit offline test double."""
import os
import json
import operator
import re
from typing import Annotated
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from app.tools import READ_TOOLS
from app.guards import ingress, egress
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

load_dotenv()
MAX_ITERATIONS = 4
Category = Literal['account', 'network', 'hardware', 'general']


class Triage(BaseModel):
    category: Category
    severity: Literal['low', 'high']


class State(TypedDict, total=False):
    findings: Annotated[list[dict], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]
    iterations: int
    fingerprints: list[str]
    escalation: str
    guardrails: list[str]
    blocked: bool
    egress_checked: bool
    summary: str
    history: list[dict]
    text: str
    category: str
    severity: str
    response: str


def model():
    from langchain_openai import ChatOpenAI
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError('MODEL_MODE=live requires OPENAI_API_KEY in .env')
    return ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), temperature=0,
                      timeout=30, max_retries=1)


def classify(state):
    if os.getenv('MODEL_MODE', 'demo') == 'live':
        result = model().with_structured_output(Triage).invoke([
            ('system', 'Classify campus IT requests. High severity: outage, security compromise, '
             'account deletion, unsafe hardware. Otherwise low.'), ('human', state['text'])])
        return result.model_dump()
    text = state['text'].lower()
    category = next((name for name, words in {
        'account': ('password', 'account', 'login', 'mfa'),
        'network': ('wifi', 'wi-fi', 'network', 'internet', 'vpn'),
        'hardware': ('laptop', 'printer', 'battery', 'hardware'),
    }.items() if any(word in text for word in words)), 'general')
    return {'category': category, 'severity': 'high' if any(
        word in text for word in ('outage', 'delete', 'compromis', 'smoke', 'swollen', 'all students')
    ) else 'low'}


def agent(state):
    iterations = state.get('iterations', 0)
    if iterations >= MAX_ITERATIONS:
        return {'messages': [AIMessage(content='Agent stopped at its iteration limit; human review required.')],
                'response': 'Agent stopped at its iteration limit; human review required.',
                'escalation': 'iteration_limit'}
    messages = state.get('messages', [])
    if os.getenv('MODEL_MODE', 'demo') == 'live':
        answer = model().bind_tools(READ_TOOLS).invoke([
            ('system', 'You are campus IT support. Use the available tools to check facts, '
             'then give concise actionable advice. Never claim to change an account.'),
            ('system', 'Previous conversation summary: ' + state.get('summary', '') + '\nRecent turns: ' +
             json.dumps(state.get('history', []))), HumanMessage(content=state['text']), *messages])
    elif not messages or not isinstance(messages[-1], ToolMessage):
        account = re.search(r'\b(?:STU|STAFF)-\d{4}\b', state['text'], re.I)
        calls = [{'name': 'search_knowledge_base', 'args': {'category': state['category']}, 'id': 'kb'}]
        if account:
            calls.append({'name': 'lookup_campus_account', 'args': {'account_id': account[0]}, 'id': 'account'})
        if state['category'] == 'network':
            calls.append({'name': 'check_service_status', 'args': {'service': 'wifi'}, 'id': 'status'})
        answer = AIMessage(content='', tool_calls=calls)
    else:
        answer = AIMessage(content='\n'.join(str(m.content) for m in messages if isinstance(m, ToolMessage)))
    fingerprints = list(state.get('fingerprints', []))
    for call in answer.tool_calls:
        fingerprint = json.dumps([call['name'], call['args']], sort_keys=True)
        if fingerprint in fingerprints:
            return {'messages': [AIMessage(content='Repeated tool call stopped; human review required.')],
                    'response': 'Repeated tool call stopped; human review required.',
                    'escalation': 'duplicate_tool_call', 'iterations': iterations + 1}
        fingerprints.append(fingerprint)
    return {'messages': [answer], 'response': str(answer.content),
            'iterations': iterations + 1, 'fingerprints': fingerprints}


def summarize(state):
    history = state.get('history', [])
    if len(history) <= 6:
        return {}
    old = state.get('summary', '')
    digest = ' | '.join(f"Request: {turn['user'][:140]}; Advice: {turn['assistant'][:180]}" for turn in history[:-2])
    # ponytail: bounded extractive summary; use model summarization if long-term semantic recall is needed.
    from langgraph.types import Overwrite
    return {'summary': (old + ' | ' + digest)[-1800:], 'history': history[-2:],
            'messages': Overwrite([state['messages'][-1]])}


def ingress_node(state):
    if state.get('blocked'):
        return {}
    result = ingress(state['text'], bool(state.get('history')))
    result['guardrails'] = list(dict.fromkeys(state.get('guardrails', []) + result['guardrails']))
    return result


def build_triage():
    graph = StateGraph(State)
    graph.add_node('classify', classify)
    graph.add_edge(START, 'classify')
    graph.add_edge('classify', END)
    return graph.compile()


def build_research():
    graph = StateGraph(State)
    graph.add_node('agent', agent)
    graph.add_node('tools', ToolNode(READ_TOOLS))
    graph.add_edge(START, 'agent')
    graph.add_conditional_edges('agent', lambda state: 'tools' if state['messages'][-1].tool_calls else END)
    graph.add_edge('tools', 'agent')
    return graph.compile()


def build_graph(checkpointer=None):
    graph = StateGraph(State)
    graph.add_node('ingress', ingress_node)
    graph.add_node('blocked', lambda state: {'response': 'This request was blocked. I can help with campus IT issues.'})
    graph.add_node('triage', build_triage())
    graph.add_node('research', build_research())
    graph.add_node('egress', egress)
    graph.add_node('finish', lambda state: {'history': state.get('history', []) + [
        {'user': state['text'], 'assistant': state['response']}]})
    graph.add_node('summarize', summarize)
    graph.add_edge(START, 'ingress')
    graph.add_conditional_edges('ingress', lambda state: 'blocked' if state.get('blocked') else 'triage')
    graph.add_edge('blocked', 'egress')
    graph.add_edge('triage', 'research')
    graph.add_edge('research', 'egress')
    graph.add_edge('egress', 'finish')
    graph.add_edge('finish', 'summarize')
    graph.add_edge('summarize', END)
    return graph.compile(checkpointer=checkpointer)
