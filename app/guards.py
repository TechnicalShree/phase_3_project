"""Deterministic guardrails run before any model call; intentionally conservative."""
import logging
import re

log = logging.getLogger(__name__)
PII = [
    (re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I), '[EMAIL]'),
    (re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)'), '[CARD]'),
    (re.compile(r'(?<!\w)(?:\+?\d[ .()-]?){10,12}(?!\w)'), '[PHONE]'),
    (re.compile(r'\b((?i:my name is|name\s*:))\s+[A-Za-z]+(?:\s+[A-Z][a-z]+){0,3}'), r'\1 [NAME]'),
]
INJECTION = re.compile(
    r'ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|system|above)|'
    r'(?:reveal|show|print|override|bypass)\b.{0,35}\b(?:prompt|instructions|secret|approval|guardrail)|'
    r'\b(?:system\s*prompt|developer\s*message|jailbreak)\b|'
    r'<\|(?:im_start|system)|\[INST\]', re.I)
DOMAIN = re.compile(r'\b(?:campus|IT|help|password|account|login|mfa|wifi|wi-fi|network|internet|vpn|'
                    r'laptop|printer|battery|hardware|outage|computer|access|student|STU-\d+|STAFF-\d+)\b', re.I)


def redact(text):
    for pattern, replacement in PII:
        text = pattern.sub(replacement, text)
    return text


def ingress(text, has_history=False):
    flags = []
    if INJECTION.search(text):
        flags.append('prompt_injection_blocked')
    elif not DOMAIN.search(text) and not (has_history and re.fullmatch(
            r'(thanks|thank you|yes|no|still not working|please continue|what next)[.!? ]*', text, re.I)):
        flags.append('off_topic_blocked')
    safe = redact(text)
    if safe != text:
        flags.append('pii_redacted')
    blocked = any(flag.endswith('_blocked') for flag in flags)
    if flags:
        log.warning('Ingress guardrails: %s', ', '.join(flags))
    return {'text': '[Blocked campus request]' if blocked else safe, 'blocked': blocked, 'guardrails': flags}


def egress(state):
    response = redact(state.get('response', ''))
    flags = list(state.get('guardrails', []))
    if response != state.get('response', ''):
        flags.append('egress_pii_redacted')
    if INJECTION.search(response):
        response = 'Unsafe generated content was withheld. Please contact the campus IT desk.'
        flags.append('egress_injection_blocked')
    if re.search(r'\b(?:maybe|not sure|I guess|probably)\b', response, re.I):
        flags.append('uncertainty_review')
        response += '\nThis advice is uncertain; verify it with the campus IT desk before acting.'
    if not response.strip():
        response = 'No reliable answer was produced. Please contact the campus IT desk.'
        flags.append('empty_response')
    if flags:
        log.info('Egress guardrails: %s', ', '.join(flags))
    return {'response': response, 'guardrails': flags, 'egress_checked': True}
