"""Small, fictional campus dataset. No external accounts are accessed."""
from langchain_core.tools import tool

CAMPUS = {
    'STU-1001': {'role': 'student', 'status': 'active', 'mfa': 'enrolled', 'residence': 'North Hall'},
    'STU-1002': {'role': 'student', 'status': 'locked', 'mfa': 'recovery_required', 'residence': 'East Hall'},
    'STAFF-2001': {'role': 'staff', 'status': 'active', 'mfa': 'enrolled', 'residence': 'Library'},
}
KB = {
    'account': 'Use the campus password portal. MFA recovery requires an in-person ID check. '
               'Account deletion must be reviewed by an authorized administrator; never delete automatically.',
    'network': 'Check the campus status page, reconnect to Campus-Secure, and renew the device DHCP lease. '
               'North Hall access point NH-02 is degraded. Building-wide outages require a network ticket.',
    'hardware': 'Record the asset tag and disconnect unsafe devices. Do not charge swollen batteries. '
                'A technician must inspect smoke, heat, liquid damage, or battery swelling.',
    'general': 'Campus IT supports accounts, Wi-Fi, VPN, printers and laptops. The desk is open 08:00–18:00.',
}


@tool
def lookup_campus_account(account_id: str) -> dict:
    """Look up a fictional campus account, e.g. STU-1001; never return names or contact details."""
    return CAMPUS.get(account_id.upper(), {'status': 'not_found', 'advice': 'Ask for a campus account ID.'})


@tool
def search_knowledge_base(category: str) -> str:
    """Get campus troubleshooting instructions for account, network, hardware or general."""
    return KB.get(category, KB['general'])


@tool
def check_service_status(service: str) -> dict:
    """Check the mock status of wifi, vpn or login campus services."""
    return {'service': service, 'status': 'degraded' if service.lower() in ('wifi', 'network') else 'operational',
            'source': 'mock campus status registry'}


READ_TOOLS = [lookup_campus_account, search_knowledge_base, check_service_status]

# The write tool is deliberately excluded from READ_TOOLS / the research ToolNode.
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Annotated, Literal
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedState
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field
from app.guards import INJECTION, redact


class TicketDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=5, max_length=120)
    details: str = Field(min_length=5, max_length=2000)
    category: Literal['account', 'network', 'hardware', 'general']
    action: Literal['incident', 'account_deletion_review'] = 'incident'


def clean_draft(draft):
    draft = TicketDraft.model_validate(draft).model_dump()
    if any(INJECTION.search(draft[key]) for key in ('title', 'details')):
        raise ValueError('Ticket text contains a blocked instruction.')
    for key in ('title', 'details'):
        draft[key] = redact(draft[key])
    return TicketDraft.model_validate(draft).model_dump()


def ticket_db(directory):
    connection = sqlite3.connect(Path(directory) / 'tickets.sqlite')
    connection.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
        thread_id TEXT NOT NULL, payload TEXT NOT NULL,
        decision TEXT NOT NULL CHECK(decision IN ('approve','edit')),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
    return connection


@tool
def create_ticket(title: str, details: str, category: str, action: str,
                  state: Annotated[dict, InjectedState], config: RunnableConfig) -> dict:
    """Create a mock campus incident or account-deletion review ticket after mandatory human approval.

    Only high-severity cases are eligible. This never deletes an account.
    """
    if state.get('severity') != 'high' or state.get('blocked'):
        raise PermissionError('Only unblocked high-severity requests may create tickets.')
    draft = clean_draft({'title': title, 'details': details, 'category': category, 'action': action})
    decision = interrupt({'kind': 'create_ticket', 'draft': draft,
                          'notice': 'Creates a mock service-desk record. No account will be deleted.'})
    if not isinstance(decision, dict) or decision.get('decision') not in ('approve', 'deny', 'edit'):
        raise ValueError('Explicit approve, deny, or edit decision required.')
    if decision['decision'] == 'deny':
        return {'status': 'denied'}
    if decision['decision'] == 'edit':
        draft = clean_draft(decision['draft'])
    thread_id = config['configurable']['thread_id']
    payload = json.dumps(draft, sort_keys=True)
    key = hashlib.sha256((thread_id + '\n' + payload).encode()).hexdigest()
    db = ticket_db(config['configurable']['data_dir'])
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO tickets(idempotency_key, thread_id, payload, decision) VALUES (?,?,?,?)',
                       (key, thread_id, payload, decision['decision']))
            row = db.execute('SELECT id, created_at FROM tickets WHERE idempotency_key=?', (key,)).fetchone()
        return {'status': 'created', 'ticket_id': f'IT-{row[0]:05d}', 'created_at': row[1], 'draft': draft}
    finally:
        db.close()
