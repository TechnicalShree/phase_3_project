"""Campus IT graph. MODEL_MODE=demo is an explicit offline test double."""
import os
import re
from typing import Annotated
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from app.tools import READ_TOOLS
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

load_dotenv()
Category = Literal['account', 'network', 'hardware', 'general']


class Triage(BaseModel):
    category: Category
    severity: Literal['low', 'high']


class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
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
    messages = state.get('messages', [])
    if os.getenv('MODEL_MODE', 'demo') == 'live':
        answer = model().bind_tools(READ_TOOLS).invoke([
            ('system', 'You are campus IT support. Use the available tools to check facts, '
             'then give concise actionable advice. Never claim to change an account.'),
            HumanMessage(content=state['text']), *messages])
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
    return {'messages': [answer], 'response': str(answer.content)}


def build_graph(checkpointer=None):
    graph = StateGraph(State)
    graph.add_node('classify', classify)
    graph.add_edge(START, 'classify')
    graph.add_node('agent', agent)
    graph.add_node('tools', ToolNode(READ_TOOLS))
    graph.add_edge('classify', 'agent')
    graph.add_conditional_edges('agent', lambda state: 'tools' if state['messages'][-1].tool_calls else END)
    graph.add_edge('tools', 'agent')
    return graph.compile(checkpointer=checkpointer)
