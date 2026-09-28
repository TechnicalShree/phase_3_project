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
