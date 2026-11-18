import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.schemas import AnalysisOutput
from app.storage import session
from app.services import tickets
from app.workers.dispatcher import dispatch_once

KEY='local-test-service-key'
PAYLOAD={'title':'Internet sem acesso','description':'Não consigo acessar a internet no computador do setor.',
         'reported_impact':'Um computador afetado','impact_scope':'individual'}


def fake_analyzer(row):
    return AnalysisOutput(category='network',suggested_priority='medium',
                          summary='Falha de internet em uma estação',
                          recommendations=['Verificar cabo','Checar conexão'],review_reason='')


@pytest.fixture
def service(tmp_path):
    db=tmp_path/'tickets.sqlite'
    app=create_app(database=db,analyzer=fake_analyzer,internal_key=KEY)
    with TestClient(app) as client:
        yield client,db


def created(service,kwargs=None):
    c,_=service
    response=c.post('/tickets',json=(kwargs or PAYLOAD))
    assert response.status_code==201,response.text
    return response.json()


def internal(service,path,body):
    c,_=service
    return c.post(path,headers={'X-Service-Key':KEY},json=body)


def test_create_and_outbox_atomic(service):
    c,db=service
    assert c.get('/health').json()=={'status':'ok'}
    item=created(service)
    assert item['ticket_id']=='TCK-0001'
    detail=c.get('/tickets/TCK-0001').json()
    assert detail['ticket_status']=='created'
    assert len(detail['history'])==1
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM outbox_events').fetchone()[0]==1
        assert s.execute('SELECT state FROM outbox_events').fetchone()[0]=='pending'
    assert len(c.get('/tickets').json())==1


def test_validation_and_unknown_ticket(service):
    c,_=service
    assert c.post('/tickets',json={'title':'a','description':'b'}).status_code==422
    assert c.get('/tickets/TCK-9999').status_code==404


def test_auth_event_mismatch_and_success(service):
    c,db=service
    t=created(service)
    url=f'/internal/tickets/{t["ticket_id"]}/analyze'
    assert c.post(url,json={'event_id':t['event_id']}).status_code==401
    assert internal(service,url,{'event_id':'11111111-1111-1111-1111-111111111111'}).status_code==409
    ok=internal(service,url,{'event_id':t['event_id']})
    assert ok.status_code==200,ok.text
    assert ok.json()['category']=='network'
    assert ok.json()['effective_priority']=='medium'
    assert ok.json()['requires_human_review'] is False
    assert c.get('/tickets/TCK-0001').json()['ticket_status']=='triaged'


def test_idempotency_same_event_no_duplicate_analysis(service):
    c,db=service
    t=created(service)
    path=f'/internal/tickets/{t["ticket_id"]}/analyze'
    assert internal(service,path,{'event_id':t['event_id']}).status_code==200
    assert internal(service,path,{'event_id':t['event_id']}).status_code==200
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM analysis_results').fetchone()[0]==1


def test_critical_suggestion_requires_review_not_auto_critical(tmp_path):
    def critical(row):
        return AnalysisOutput(category='network',suggested_priority='critical',summary='Toda internet caiu',
                              recommendations=['Consultar equipamentos'],review_reason='Possível impacto geral')
    with TestClient(create_app(database=tmp_path/'db.sqlite',analyzer=critical,internal_key=KEY)) as c:
        t=c.post('/tickets',json=PAYLOAD).json()
        resp=c.post(f'/internal/tickets/{t["ticket_id"]}/analyze',
                    json={'event_id':t['event_id']},headers={'X-Service-Key':KEY})
        assert resp.status_code==200
        assert resp.json()['effective_priority']=='high'
        assert resp.json()['requires_human_review'] is True
        assert c.get('/tickets/TCK-0001').json()['ticket_status']=='awaiting_review'


def test_provider_failure_does_not_delete_ticket(tmp_path):
    def fail(row):
        raise RuntimeError('provider offline with private details')
    with TestClient(create_app(database=tmp_path/'db.sqlite',analyzer=fail,internal_key=KEY)) as c:
        t=c.post('/tickets',json=PAYLOAD).json()
        resp=c.post(f'/internal/tickets/{t["ticket_id"]}/analyze',
                    json={'event_id':t['event_id']},headers={'X-Service-Key':KEY})
        assert resp.status_code==502
        assert resp.json()['error_code']=='ANALYSIS_FAILED'
        d=c.get('/tickets/TCK-0001').json()
        assert d['ticket_status']=='awaiting_review'
        assert d['analysis_status']=='failed'
        assert 'private details' not in resp.text


def test_sync_success_and_dedupe(service):
    c,db=service
    t=created(service)
    url=f'/internal/tickets/{t["ticket_id"]}'
    internal(service,url+'/analyze',{'event_id':t['event_id']})
    b={'event_id':t['event_id'],'status':'succeeded'}
    assert internal(service,url+'/sync-status',b).json()['event_state']=='completed'
    assert internal(service,url+'/sync-status',b).status_code==200
    with session(db) as s:
        assert s.execute('SELECT COUNT(*) FROM external_syncs').fetchone()[0]==1
        assert s.execute('SELECT state FROM outbox_events').fetchone()[0]=='completed'


def test_sheets_failure_sets_retry(service):
    c,db=service
    t=created(service)
    url=f'/internal/tickets/{t["ticket_id"]}'
    internal(service,url+'/analyze',{'event_id':t['event_id']})
    b={'event_id':t['event_id'],'status':'failed','failure_stage':'sync','error_code':'SHEETS_SYNC_FAILED'}
    assert internal(service,url+'/sync-status',b).json()['event_state']=='retry'
    assert c.get('/tickets/TCK-0001').json()['analysis_status']=='succeeded'


def test_human_only_status_and_resolution(service):
    c,db=service
    t=created(service)
    url=f'/tickets/{t["ticket_id"]}/status'
    assert c.patch(url,json={'status':'closed'}).status_code==403
    h={'X-Demo-Role':'attendant'}
    assert c.patch(url,headers=h,json={'status':'closed'}).status_code==409
    assert c.patch(url,headers=h,json={'status':'in_progress'}).status_code==200
    assert c.patch(url,headers=h,json={'status':'resolved'}).status_code==422
    assert c.patch(url,headers=h,json={'status':'resolved','resolution_notes':'Ajuste no roteador concluído.'}).status_code==200
    assert c.patch(url,headers=h,json={'status':'closed'}).status_code==200
    d=c.get('/tickets/TCK-0001').json()
    assert d['ticket_status']=='closed'
    assert len(d['history'])==4
    assert c.patch(url,headers=h,json={'status':'in_progress'}).status_code==409


def test_dispatcher_retries_if_n8n_down(service,monkeypatch):
    import httpx
    c,db=service
    created(service)
    monkeypatch.setenv('N8N_WEBHOOK_KEY','demo-key')
    def handler(req):
        raise httpx.ConnectError('n8n offline')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert dispatch_once(db,client) is True
    with session(db) as s:
        row=s.execute('SELECT state,attempts,last_error FROM outbox_events').fetchone()
        assert row['state']=='retry'
        assert row['attempts']==1
        assert row['last_error']=='WEBHOOK_DELIVERY_FAILED'


def test_attendant_priority_review_is_audited(service):
    c,db=service
    t=created(service)
    path=f'/tickets/{t["ticket_id"]}/priority'
    body={'priority':'high','reason':'Impacto confirmado pelo atendimento'}
    assert c.patch(path,json=body).status_code==403
    assert c.patch(path,headers={'X-Demo-Role':'attendant'},json=body).status_code==200
    detail=c.get(f'/tickets/{t["ticket_id"]}').json()
    assert detail['effective_priority']=='high'
    assert detail['priority_reviews'][0]['previous_priority'] is None
    assert detail['priority_reviews'][0]['new_priority']=='high'
    assert detail['priority_reviews'][0]['reason']==body['reason']
    assert c.patch(path,headers={'X-Demo-Role':'attendant'},json={**body,'priority':'critical'}).status_code==422


def test_retry_failed_analysis_creates_distinct_event_and_history(tmp_path):
    calls=[0]
    def unstable(ticket):
        calls[0]+=1
        if calls[0]==1:
            raise RuntimeError('OpenAI offline')
        return fake_analyzer(ticket)
    db=tmp_path/'retry.sqlite'
    with TestClient(create_app(database=db,analyzer=unstable,internal_key=KEY)) as c:
        t=c.post('/tickets',json=PAYLOAD).json()
        base=f'/internal/tickets/{t["ticket_id"]}'
        assert c.post(base+'/analyze',json={'event_id':t['event_id']},headers={'X-Service-Key':KEY}).status_code==502
        endpoint=f'/tickets/{t["ticket_id"]}/retry-analysis'
        assert c.post(endpoint).status_code==403
        retry=c.post(endpoint,headers={'X-Demo-Role':'attendant'})
        assert retry.status_code==202
        new_event=retry.json()['event_id']
        assert new_event!=t['event_id']
        assert c.post(endpoint,headers={'X-Demo-Role':'attendant'}).status_code==409
        result=c.post(base+'/analyze',json={'event_id':new_event},headers={'X-Service-Key':KEY})
        assert result.status_code==200,result.text
        assert c.get(f'/tickets/{t["ticket_id"]}').json()['analysis_status']=='succeeded'
        with session(db) as s:
            attempts=s.execute('SELECT attempt_number,status FROM analysis_results ORDER BY attempt_number').fetchall()
            assert [(r['attempt_number'],r['status']) for r in attempts]==[(1,'failed'),(2,'succeeded')]
            assert s.execute('SELECT COUNT(*) FROM outbox_events').fetchone()[0]==2
        old_callback=c.post(base+'/sync-status',headers={'X-Service-Key':KEY},json={
            'event_id':t['event_id'],'status':'failed','failure_stage':'analysis','error_code':'ANALYSIS_FAILED'})
        assert old_callback.status_code==409
        assert old_callback.json()['error_code']=='STALE_EVENT_CALLBACK'


def test_running_analysis_cannot_overwrite_manual_priority(tmp_path):
    # A revisão é rejeitada durante a análise; não há condição de corrida de prioridade.
    db=tmp_path/'inflight.sqlite'
    from app.schemas import PriorityReview
    from app.services.tickets import review_priority,DomainError
    def inspecting(ticket):
        with pytest.raises(DomainError) as ex:
            review_priority(db,ticket['public_id'],PriorityReview(priority='high',reason='Conferido pelo atendente'))
        assert ex.value.code=='ANALYSIS_IN_PROGRESS'
        return fake_analyzer(ticket)
    with TestClient(create_app(database=db,analyzer=inspecting,internal_key=KEY)) as c:
        t=c.post('/tickets',json=PAYLOAD).json()
        r=c.post(f'/internal/tickets/{t["ticket_id"]}/analyze',headers={'X-Service-Key':KEY},json={'event_id':t['event_id']})
        assert r.status_code==200,r.text


def test_provider_model_traceability_and_utf8(tmp_path):
    from app.services.ai import ProviderAnalysis
    db=tmp_path/'trace.sqlite'
    def provider(row):
        return ProviderAnalysis(
            output=AnalysisOutput(category='access',suggested_priority='high',
                summary='Vários funcionários não conseguem acessar o sistema.',
                recommendations=['Verificar conexão e permissões sem solicitar senhas.'],
                review_reason='Revisão necessária por impacto incerto.'),
            provider_model='provider-reported-model-001')
    with TestClient(create_app(database=db,analyzer=provider,internal_key=KEY)) as c:
        t=c.post('/tickets',json=PAYLOAD).json()
        response=c.post(f'/internal/tickets/{t["ticket_id"]}/analyze',
          headers={'X-Service-Key':KEY},json={'event_id':t['event_id']})
        assert response.status_code==200,response.text
        detail=c.get(f'/tickets/{t["ticket_id"]}').json()
        assert detail['analysis']['model_name']=='test-adapter'
        assert detail['analysis']['provider_model']=='provider-reported-model-001'
        assert detail['analysis']['summary']=='Vários funcionários não conseguem acessar o sistema.'
        assert 'conexão' in detail['analysis']['recommendations'][0]
        assert 'nÃ£o' not in response.text
        with session(db) as conn:
            val=conn.execute('SELECT provider_model,summary FROM analysis_results').fetchone()
            assert val['provider_model']=='provider-reported-model-001'
            assert 'Vários' in val['summary']


def test_additive_migration_preserves_old_database(tmp_path):
    import sqlite3
    from app.storage import init_db
    db=tmp_path/'legacy.sqlite'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE analysis_results (id TEXT PRIMARY KEY, model_name TEXT)')
        conn.execute("INSERT INTO analysis_results (id,model_name) VALUES ('old','configured-model')")
    init_db(db)
    init_db(db)
    with sqlite3.connect(db) as conn:
        row=conn.execute("SELECT model_name,provider_model FROM analysis_results WHERE id='old'").fetchone()
        assert row==('configured-model',None)
