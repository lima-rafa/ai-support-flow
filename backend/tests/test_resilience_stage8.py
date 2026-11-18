"""Etapa 8: testes isolados de falhas e idempotencia, SEM rede externa.

Cada teste utiliza SQLite temporario; a OpenAI e o n8n sao simulados.
"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import AnalysisOutput
from app.storage import session
from app.workers.dispatcher import dispatch_once

KEY = 'stage8-test-service-key'
ROLE = {'X-Demo-Role': 'attendant'}
PAYLOAD = {
    'title': 'Falha no email corporativo',
    'description': 'Um colaborador nao consegue acessar seu email de trabalho.',
    'affected_service': 'email',
    'reported_impact': 'single_user',
}


def good_result(_ticket):
    return AnalysisOutput(
        category='email', suggested_priority='medium',
        summary='Um colaborador não consegue acessar o e-mail.',
        recommendations=['Verificar mensagem de erro sem expor senhas.'],
        review_reason='A abrangência do problema deve ser confirmada.',
    )


@pytest.fixture
def env(tmp_path):
    db = tmp_path / 'stage8.sqlite'
    calls = []

    def analyzer(ticket):
        calls.append(ticket['public_id'])
        return good_result(ticket)

    with TestClient(create_app(database=db, analyzer=analyzer, internal_key=KEY)) as client:
        yield client, db, calls


def create(client):
    response = client.post('/tickets', json=PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


def cb(client, ticket, suffix, body):
    return client.post(
        f'/internal/tickets/{ticket["ticket_id"]}/{suffix}',
        json={'event_id': ticket['event_id'], **body},
        headers={'X-Service-Key': KEY},
    )


def test_duplicate_webhook_reuses_result_without_second_provider_call(env):
    client, db, calls = env
    t = create(client)
    for _ in range(3):
        r = cb(client, t, 'analyze', {})
        assert r.status_code == 200, r.text
    assert calls == [t['ticket_id']]
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM analysis_results').fetchone()[0] == 1
        assert s.execute('SELECT COUNT(*) FROM ticket_status_history').fetchone()[0] == 3


def test_callback_auth_and_wrong_event_rejected_without_mutation(env):
    client, db, calls = env
    t = create(client)
    endpoint = f'/internal/tickets/{t["ticket_id"]}/analyze'
    assert client.post(endpoint, json={'event_id': t['event_id']}).status_code == 401
    invalid = client.post(endpoint, headers={'X-Service-Key': KEY}, json={
        'event_id': '00000000-0000-0000-0000-000000000000'})
    assert invalid.status_code == 409
    assert calls == []
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM analysis_results').fetchone()[0] == 0


def test_repeated_sheets_callback_creates_single_projection_record(env):
    client, db, _ = env
    t = create(client)
    assert cb(client, t, 'analyze', {}).status_code == 200
    for _ in range(3):
        r = cb(client, t, 'sync-status', {'status': 'succeeded'})
        assert r.status_code == 200, r.text
        assert r.json()['event_state'] == 'completed'
    with session(db) as s:
        sync = s.execute('SELECT status,attempts FROM external_syncs').fetchall()
        assert len(sync) == 1
        assert sync[0]['status'] == 'succeeded'
        assert sync[0]['attempts'] == 1
        assert s.execute('SELECT state FROM outbox_events').fetchone()[0] == 'completed'


def test_sheets_failure_then_recovery_preserves_analysis(env):
    client, db, calls = env
    t = create(client)
    assert cb(client, t, 'analyze', {}).status_code == 200
    fail = cb(client, t, 'sync-status', {
        'status': 'failed', 'failure_stage': 'sync', 'error_code': 'SHEETS_SYNC_FAILED'})
    assert fail.status_code == 200 and fail.json()['event_state'] == 'retry'
    intermediate = client.get(f'/tickets/{t["ticket_id"]}').json()
    assert intermediate['analysis_status'] == 'succeeded'
    assert intermediate['sync_status'] == 'failed'
    assert intermediate['analysis']['summary'] == good_result({}).summary
    succeeded = cb(client, t, 'sync-status', {'status': 'succeeded'})
    assert succeeded.status_code == 200
    assert succeeded.json()['event_state'] == 'completed'
    assert calls == [t['ticket_id']]
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM analysis_results').fetchone()[0] == 1
        assert s.execute('SELECT COUNT(*) FROM external_syncs').fetchone()[0] == 1
        assert s.execute('SELECT state FROM outbox_events').fetchone()[0] == 'completed'


def test_webhook_network_failure_then_dispatcher_recovery(env, monkeypatch):
    client, db, _ = env
    t = create(client)
    monkeypatch.setenv('N8N_WEBHOOK_KEY', 'demo-secret')
    deliveries = []

    def down(request):
        deliveries.append(request)
        raise httpx.ConnectError('unavailable')

    with httpx.Client(transport=httpx.MockTransport(down)) as mock:
        assert dispatch_once(db, mock) is True
    with session(db) as s:
        row = s.execute('SELECT state,attempts,last_error FROM outbox_events').fetchone()
        assert tuple(row) == ('retry', 1, 'WEBHOOK_DELIVERY_FAILED')
        s.execute('UPDATE outbox_events SET next_attempt_at=? WHERE event_id=?',
                  ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(), t['event_id']))

    def up(request):
        deliveries.append(request)
        assert request.headers['X-N8N-Key'] == 'demo-secret'
        assert request.read().decode().find(t['event_id']) >= 0
        return httpx.Response(200, json={'accepted': True})

    with httpx.Client(transport=httpx.MockTransport(up)) as mock:
        assert dispatch_once(db, mock) is True
    with session(db) as s:
        row = s.execute('SELECT state,attempts FROM outbox_events').fetchone()
        assert tuple(row) == ('sent', 2)
    assert len(deliveries) == 2
    # Recebimento HTTP 200 pelo n8n nao prova conclusao: so callback encerra o evento.
    assert cb(client, t, 'analyze', {}).status_code == 200
    assert cb(client, t, 'sync-status', {'status': 'succeeded'}).status_code == 200
    with session(db) as s:
        assert s.execute('SELECT state FROM outbox_events').fetchone()[0] == 'completed'


def test_dispatcher_dead_letter_after_four_failed_deliveries(env, monkeypatch):
    client, db, _ = env
    create(client)
    monkeypatch.setenv('N8N_WEBHOOK_KEY', 'demo-secret')

    def down(_request):
        raise httpx.ConnectError('unavailable')

    with httpx.Client(transport=httpx.MockTransport(down)) as mock:
        for attempt in range(1, 5):
            assert dispatch_once(db, mock) is True
            with session(db, write=True) as s:
                row = s.execute('SELECT event_id,state,attempts FROM outbox_events').fetchone()
                assert row['attempts'] == attempt
                assert row['state'] == ('dead_letter' if attempt == 4 else 'retry')
                s.execute('UPDATE outbox_events SET next_attempt_at=? WHERE event_id=?',
                          ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(), row['event_id']))
        assert dispatch_once(db, mock) is False
    assert client.get('/tickets/TCK-0001').json()['ticket_status'] == 'created'


def test_ai_failure_then_authorized_retry_is_auditable(tmp_path):
    db = tmp_path / 'ai_retry.sqlite'
    calls = []

    def flaky(ticket):
        calls.append(ticket['public_id'])
        if len(calls) == 1:
            raise RuntimeError('private-secret-placeholder')
        return good_result(ticket)

    with TestClient(create_app(database=db, analyzer=flaky, internal_key=KEY)) as client:
        t = create(client)
        failure = cb(client, t, 'analyze', {})
        assert failure.status_code == 502
        assert 'private-secret-placeholder' not in failure.text
        assert client.get(f'/tickets/{t["ticket_id"]}').json()['analysis_status'] == 'failed'
        retry_url = f'/tickets/{t["ticket_id"]}/retry-analysis'
        assert client.post(retry_url).status_code == 403
        response = client.post(retry_url, headers=ROLE)
        assert response.status_code == 202
        new_event = response.json()['event_id']
        assert new_event != t['event_id']
        second = client.post(f'/internal/tickets/{t["ticket_id"]}/analyze',
                             headers={'X-Service-Key': KEY}, json={'event_id': new_event})
        assert second.status_code == 200
        assert len(calls) == 2
        detail = client.get(f'/tickets/{t["ticket_id"]}').json()
        assert detail['analysis_status'] == 'succeeded'
        with session(db) as s:
            attempts = s.execute('SELECT attempt_number,status,error_code FROM analysis_results ORDER BY attempt_number').fetchall()
            assert [(a['attempt_number'], a['status']) for a in attempts] == [(1, 'failed'), (2, 'succeeded')]
            assert attempts[0]['error_code'] == 'ANALYSIS_FAILED'


def test_closed_ticket_immutable_and_never_auto_closed(env):
    client, db, _ = env
    t = create(client)
    assert cb(client, t, 'analyze', {}).status_code == 200
    assert cb(client, t, 'sync-status', {'status': 'succeeded'}).status_code == 200
    detail = client.get(f'/tickets/{t["ticket_id"]}').json()
    assert detail['ticket_status'] in ('triaged', 'awaiting_review')
    endpoint = f'/tickets/{t["ticket_id"]}/status'
    assert client.patch(endpoint, json={'status': 'in_progress'}).status_code == 403
    assert client.patch(endpoint, headers=ROLE, json={'status': 'closed'}).status_code == 409
    assert client.patch(endpoint, headers=ROLE, json={'status': 'in_progress'}).status_code == 200
    assert client.patch(endpoint, headers=ROLE, json={'status': 'resolved'}).status_code == 422
    assert client.patch(endpoint, headers=ROLE, json={
        'status': 'resolved', 'resolution_notes': 'Atendimento de teste validado.'}).status_code == 200
    assert client.patch(endpoint, headers=ROLE, json={'status': 'closed'}).status_code == 200
    assert client.patch(endpoint, headers=ROLE, json={'status': 'in_progress'}).status_code == 409
    assert cb(client, t, 'analyze', {}).status_code == 409
    assert client.get(f'/tickets/{t["ticket_id"]}').json()['ticket_status'] == 'closed'
