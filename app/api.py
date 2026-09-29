"""Same-origin local UI + FastAPI; bind to loopback unless API_TOKEN is configured."""
import hmac
import json
import logging
import os
import secrets
import re
from threading import Lock
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.service import Helpdesk
from app.tools import TicketDraft

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / 'static'


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=3, max_length=4000)
    thread_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    thread_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    checkpoint_id: str = Field(min_length=1, max_length=100)
    draft: TicketDraft | None = None


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checkpoint_id: str = Field(min_length=1, max_length=100)
    category: Literal['account', 'network', 'hardware', 'general']


def authorize(request: Request):
    token = os.getenv('API_TOKEN', '')
    if getattr(request.state, 'guest_id', None) and not request.headers.get('Authorization'):
        pass
    elif token:
        if not hmac.compare_digest(request.headers.get('Authorization', ''), f'Bearer {token}'):
            raise HTTPException(401, 'Enter the configured API token.')
    elif request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, 'Remote use requires API_TOKEN.')
    origin = request.headers.get('origin')
    if request.method != 'GET' and origin and urlparse(origin).netloc != request.url.netloc:
        raise HTTPException(403, 'Cross-origin writes are not allowed.')


def create_app(directory=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.helpdesk = Helpdesk(directory or os.getenv('DATA_DIR', 'data'))
        yield
        app.state.helpdesk.close()

    guest_lock = Lock()
    app = FastAPI(title='Campus IT Desk', version='1.0.0', lifespan=lifespan)

    @app.middleware('http')
    async def guest_session(request, call_next):
        enabled = os.getenv('PUBLIC_GUEST_ACCESS') == '1'
        cookie = request.cookies.get('campus-session', '')
        identity, _, signature = cookie.partition('.')
        key = os.getenv('API_TOKEN', '')
        if enabled and key:
            if not (re.fullmatch(r'[a-f0-9]{48}', identity) and hmac.compare_digest(
                    signature, hmac.new(key.encode(), identity.encode(), 'sha256').hexdigest())):
                identity = secrets.token_hex(24)
            request.state.guest_id = identity
        response = await call_next(request)
        if enabled and key:
            signature = hmac.new(key.encode(), identity.encode(), 'sha256').hexdigest()
            response.set_cookie('campus-session', f'{identity}.{signature}', httponly=True,
                                secure=request.url.scheme == 'https', samesite='strict', max_age=2592000)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': os.getenv('MODEL_MODE', 'demo'),
                'provider': os.getenv('LLM_PROVIDER', 'openrouter'), 'auth_required': bool(os.getenv('API_TOKEN')) and os.getenv('PUBLIC_GUEST_ACCESS') != '1',
                'guest_access': os.getenv('PUBLIC_GUEST_ACCESS') == '1'}

    def service(request: Request):
        if getattr(request.state, 'guest_id', None) and not request.headers.get('Authorization'):
            # ponytail: serialize guest requests; use per-session locks for higher traffic.
            with guest_lock:
                desk = Helpdesk(Path(directory or os.getenv('DATA_DIR', 'data')) / 'guests' / request.state.guest_id)
                try:
                    yield desk
                finally:
                    desk.close()
        else:
            yield request.app.state.helpdesk

    def perform(function, *args):
        try:
            return function(*args)
        except (ValueError, PermissionError) as error:
            raise HTTPException(409, str(error)) from error
        except Exception as error:
            log.error('Graph run failed: %s', type(error).__name__)
            raise HTTPException(502, 'Graph execution failed. Check model configuration and server logs; state is preserved.') from error

    @app.post('/run', dependencies=[Depends(authorize)])
    def run(body: RunRequest, desk=Depends(service)):
        return perform(desk.run_ticket, body.text, body.thread_id)

    @app.post('/stream', dependencies=[Depends(authorize)])
    def stream(body: RunRequest, desk=Depends(service)):
        def events():
            try:
                for event in desk.stream_ticket(body.text, body.thread_id):
                    yield 'data: ' + json.dumps(event, default=str) + '\n\n'
            except Exception as error:
                log.error('Streaming run failed: %s', type(error).__name__)
                yield 'data: ' + json.dumps({'event': 'error', 'message': 'Run failed or thread has unfinished work. Reload the thread and check server configuration.'}) + '\n\n'
        return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.get('/threads', dependencies=[Depends(authorize)])
    def threads(desk=Depends(service)):
        return desk.threads()

    @app.get('/threads/{thread_id}', dependencies=[Depends(authorize)])
    def thread(thread_id: str, desk=Depends(service)):
        result = desk.snapshot(thread_id)
        if not result['values']:
            raise HTTPException(404, 'Thread not found.')
        return result

    @app.get('/pending-approvals', dependencies=[Depends(authorize)])
    def pending(desk=Depends(service)):
        return [thread for thread in desk.threads() if thread['pending']]

    def review(decision, body, desk):
        if decision == 'edit' and body.draft is None:
            raise HTTPException(422, 'Edited draft is required.')
        return perform(desk.resume, body.thread_id, decision, body.checkpoint_id,
                       body.draft.model_dump() if body.draft else None)

    @app.post('/approve', dependencies=[Depends(authorize)])
    def approve(body: ReviewRequest, desk=Depends(service)):
        return review('approve', body, desk)

    @app.post('/deny', dependencies=[Depends(authorize)])
    def deny(body: ReviewRequest, desk=Depends(service)):
        return review('deny', body, desk)

    @app.post('/edit-and-approve', dependencies=[Depends(authorize)])
    def edit_and_approve(body: ReviewRequest, desk=Depends(service)):
        return review('edit', body, desk)

    @app.get('/forensics/{thread_id}', dependencies=[Depends(authorize)])
    def forensics(thread_id: str, desk=Depends(service)):
        return desk.forensics(thread_id)

    @app.post('/threads/{thread_id}/time-travel', dependencies=[Depends(authorize)])
    def time_travel(thread_id: str, body: ReplayRequest, desk=Depends(service)):
        return perform(desk.time_travel, thread_id, body.checkpoint_id, body.category)

    @app.post('/threads/{thread_id}/demo-fault', dependencies=[Depends(authorize)])
    def demo_fault(thread_id: str, desk=Depends(service)):
        if os.getenv('MODEL_MODE', 'demo') != 'demo':
            raise HTTPException(403, 'Fault injection is available only in offline demo mode.')
        return perform(desk.demo_fault, thread_id)

    @app.get('/tickets', dependencies=[Depends(authorize)])
    def tickets(desk=Depends(service)):
        return desk.tickets()

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    return app


app = create_app()
