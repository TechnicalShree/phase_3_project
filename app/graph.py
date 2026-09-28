"""Campus IT graph. MODEL_MODE=demo is an explicit offline test double."""
import os
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


def build_graph(checkpointer=None):
    graph = StateGraph(State)
    graph.add_node('classify', classify)
    graph.add_edge(START, 'classify')
    for category in ('account', 'network', 'hardware', 'general'):
        graph.add_node(category, lambda state: {'response': f"Routed to {state['category']} support."})
        graph.add_edge(category, END)
    graph.add_conditional_edges('classify', lambda state: state['category'])
    return graph.compile(checkpointer=checkpointer)
