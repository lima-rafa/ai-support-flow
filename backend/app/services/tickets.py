"""Casos de uso independentes das rotas FastAPI."""
import json
import uuid
from datetime import datetime, timezone, timedelta
from ..storage import session, row_as_dict
from .rules import apply_rules
from .ai import PROMPT_VERSION


def now():
    return datetime.now(timezone.utc).isoformat()


def identity():
    return str(uuid.uuid4())


class DomainError(Exception):
    def __init__(self, code, http_status=409):
        self.code, self.http_status = code, http_status
        super().__init__(code)


def status_event(db, ticket_id, previous, following, actor, reason=None):
    if previous == following:
        return
    db.execute('''INSERT INTO ticket_status_history
        (id,ticket_id,previous_status,new_status,actor_type,reason,created_at)
        VALUES (?,?,?,?,?,?,?)''',
        (identity(),ticket_id,previous,following,actor,reason,now()))


def create_ticket(path, payload):
    t = now()
    with session(path, write=True) as db:
        sequence = db.execute('INSERT INTO ticket_numbers DEFAULT VALUES').lastrowid
        public_id = f'TCK-{sequence:04d}'
        ticket_id, event_id = identity(), identity()
        db.execute('''INSERT INTO tickets
          (id,public_id,title,description,affected_service,reported_impact,
           impact_scope,ticket_status,analysis_status,sync_status,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,'created','pending','pending',?,?)''',
          (ticket_id,public_id,payload.title.strip(),payload.description.strip(),
           payload.affected_service,payload.reported_impact,payload.impact_scope,t,t))
        body = {'event_id':event_id,'event_type':'ticket.created','ticket_id':public_id}
        db.execute('''INSERT INTO outbox_events
          (event_id,ticket_id,event_type,payload_json,state,next_attempt_at,created_at)
          VALUES (?,?,?,?,'pending',?,?)''',
          (event_id,ticket_id,'ticket.created',json.dumps(body),t,t))
        status_event(db,ticket_id,None,'created','system','Chamado criado')
    return {'ticket_id':public_id,'ticket_status':'created','event_id':event_id}


def get_ticket(path, public_id):
    with session(path) as db:
        row = db.execute('SELECT * FROM tickets WHERE public_id=?',(public_id,)).fetchone()
        if not row:
            raise DomainError('TICKET_NOT_FOUND',404)
        result = row_as_dict(row)
        a = db.execute('''SELECT event_id,status,category,suggested_priority,summary,
          recommendations_json,review_reason,requires_human_review,effective_priority,
          model_name,provider_model,prompt_version,error_code,created_at FROM analysis_results
          WHERE ticket_id=? ORDER BY created_at DESC LIMIT 1''',(row['id'],)).fetchone()
        if a:
            result['analysis'] = row_as_dict(a)
            result['analysis']['recommendations'] = json.loads(result['analysis'].pop('recommendations_json') or '[]')
            if result['analysis']['requires_human_review'] is not None:
                result['analysis']['requires_human_review'] = bool(result['analysis']['requires_human_review'])
        else:
            result['analysis'] = None
        result['priority_reviews']=[row_as_dict(r) for r in db.execute(
          '''SELECT previous_priority,new_priority,actor_type,reason,created_at
          FROM priority_review_history WHERE ticket_id=? ORDER BY created_at,id''',(row['id'],))]
        result['history']=[row_as_dict(r) for r in db.execute(
          '''SELECT previous_status,new_status,actor_type,reason,created_at
          FROM ticket_status_history WHERE ticket_id=? ORDER BY created_at,id''',(row['id'],))]
        result.pop('id')
        return result


def list_tickets(path):
    with session(path) as db:
        return [row_as_dict(r) for r in db.execute('''SELECT public_id AS ticket_id,title,
            ticket_status,analysis_status,sync_status,effective_priority,created_at,updated_at
            FROM tickets ORDER BY created_at DESC,public_id DESC LIMIT 100''')]


def check_event(db, public_id, event_id):
    try:
        uuid.UUID(event_id)
    except (TypeError, ValueError):
        raise DomainError('INVALID_EVENT_ID',422)
    row=db.execute('''SELECT o.event_id,o.state,o.ticket_id,t.ticket_status,t.impact_scope
    FROM outbox_events o JOIN tickets t ON o.ticket_id=t.id
    WHERE o.event_id=? AND t.public_id=?''',(event_id,public_id)).fetchone()
    if not row:
        raise DomainError('EVENT_MISMATCH',409)
    return row


def pack_analysis(db, ticket_id, event_id, public_id):
    a=db.execute('''SELECT * FROM analysis_results WHERE event_id=? AND ticket_id=?''',
                (event_id,ticket_id)).fetchone()
    if a is None:
        raise DomainError('ANALYSIS_NOT_FOUND',409)
    if a['status'] != 'succeeded':
        raise DomainError('ANALYSIS_NOT_COMPLETED',409)
    return {
        'ticket_id':public_id,'event_id':event_id,'category':a['category'],
        'suggested_priority':a['suggested_priority'],
        'effective_priority':a['effective_priority'],
        'summary':a['summary'],
        'recommendations':json.loads(a['recommendations_json']),
        'requires_human_review':bool(a['requires_human_review']),
        'review_reason':a['review_reason'],
    }


def analyze(path, public_id, event_id, analyzer, model_name):
    with session(path,write=True) as db:
        e=check_event(db,public_id,event_id)
        if e['ticket_status'] in ('resolved','closed'):
            raise DomainError('TICKET_ALREADY_RESOLVED')
        existing=db.execute('SELECT status FROM analysis_results WHERE event_id=?',
                            (event_id,)).fetchone()
        if existing:
            if existing['status']=='succeeded':
                return pack_analysis(db,e['ticket_id'],event_id,public_id)
            raise DomainError('ANALYSIS_ALREADY_STARTED_OR_FAILED')
        row=db.execute('SELECT * FROM tickets WHERE id=?',(e['ticket_id'],)).fetchone()
        attempt=db.execute('SELECT COALESCE(MAX(attempt_number),0)+1 FROM analysis_results WHERE ticket_id=?',(e['ticket_id'],)).fetchone()[0]
        db.execute('''INSERT INTO analysis_results
          (id,ticket_id,event_id,attempt_number,status,prompt_version,model_name,created_at,updated_at)
          VALUES (?,?,?,?,'running',?,?,?,?)''',
          (identity(),e['ticket_id'],event_id,attempt,PROMPT_VERSION,model_name,now(),now()))
        if e['ticket_status'] in ('created','awaiting_review','triaged'):
            db.execute("UPDATE tickets SET analysis_status='running',ticket_status='processing',updated_at=? WHERE id=?",
                       (now(),e['ticket_id']))
            status_event(db,e['ticket_id'],e['ticket_status'],'processing','system','Análise iniciada pelo n8n')
        else:
            db.execute("UPDATE tickets SET analysis_status='running',updated_at=? WHERE id=?",(now(),e['ticket_id']))
        ticket=row_as_dict(row)
    try:
        from ..schemas import AnalysisOutput
        from .ai import ProviderAnalysis
        raw=analyzer(ticket)
        provider_model=raw.provider_model if isinstance(raw,ProviderAnalysis) else None
        result=AnalysisOutput.model_validate(raw.output if isinstance(raw,ProviderAnalysis) else raw)
        effective,human,reason=apply_rules(result,ticket['impact_scope'])
    except Exception:
        with session(path,write=True) as db:
            row=db.execute('SELECT ticket_status FROM tickets WHERE id=?',(e['ticket_id'],)).fetchone()
            db.execute("UPDATE analysis_results SET status='failed',error_code='ANALYSIS_FAILED',updated_at=? WHERE event_id=?",
                       (now(),event_id))
            if row['ticket_status']=='processing':
                db.execute("UPDATE tickets SET analysis_status='failed',ticket_status='awaiting_review',updated_at=? WHERE id=?",
                           (now(),e['ticket_id']))
                status_event(db,e['ticket_id'],'processing','awaiting_review','system','Falha da IA: revisão manual')
        raise DomainError('ANALYSIS_FAILED',502)
    invalid=False
    analysis_result=None
    with session(path,write=True) as db:
        row=db.execute('SELECT ticket_status FROM tickets WHERE id=?',(e['ticket_id'],)).fetchone()
        if row['ticket_status'] not in ('processing','in_progress'):
            # Um agente não deve reabrir ou modificar chamado já resolvido.
            db.execute("UPDATE analysis_results SET status='failed',error_code='TICKET_CHANGED_DURING_ANALYSIS',updated_at=? WHERE event_id=?", (now(),event_id))
            invalid=True
        else:
            db.execute('''UPDATE analysis_results SET status='succeeded',category=?,
              suggested_priority=?,summary=?,recommendations_json=?,review_reason=?,
              requires_human_review=?,effective_priority=?,provider_model=?,updated_at=? WHERE event_id=?''',
              (result.category,result.suggested_priority,result.summary,
               json.dumps(result.recommendations,ensure_ascii=False),reason,int(human),effective,provider_model,now(),event_id))
            following='awaiting_review' if human else 'triaged'
            if row['ticket_status']=='processing':
                db.execute('''UPDATE tickets SET analysis_status='succeeded',ticket_status=?,
                  effective_priority=?,updated_at=? WHERE id=?''',(following,effective,now(),e['ticket_id']))
                status_event(db,e['ticket_id'],'processing',following,'system','Triagem concluída')
            else:
                # O atendente já assumiu o caso: não reverter seu avanço.
                db.execute('''UPDATE tickets SET analysis_status='succeeded',
                  effective_priority=?,updated_at=? WHERE id=?''',(effective,now(),e['ticket_id']))
            analysis_result=pack_analysis(db,e['ticket_id'],event_id,public_id)
    if invalid:
        raise DomainError('TICKET_CHANGED_DURING_ANALYSIS')
    return analysis_result


def sync_result(path,public_id,event_id,status,failure_stage,error_code=None):
    if status=='succeeded' and failure_stage!='none':
        raise DomainError('INCONSISTENT_SYNC_PAYLOAD',422)
    if status=='failed' and failure_stage=='none':
        raise DomainError('FAILURE_STAGE_REQUIRED',422)
    with session(path,write=True) as db:
        e=check_event(db,public_id,event_id)
        a=db.execute('SELECT status FROM analysis_results WHERE event_id=?',(event_id,)).fetchone()
        if not a:
            raise DomainError('ANALYSIS_NOT_FOUND')
        latest=db.execute('SELECT event_id FROM analysis_results WHERE ticket_id=? ORDER BY attempt_number DESC LIMIT 1',(e['ticket_id'],)).fetchone()
        if latest and latest['event_id']!=event_id:
            raise DomainError('STALE_EVENT_CALLBACK')
        if status=='succeeded' and a['status']!='succeeded':
            raise DomainError('ANALYSIS_NOT_COMPLETED')
        already=db.execute('SELECT status FROM external_syncs WHERE ticket_id=? AND provider=?',
                           (e['ticket_id'],'google_sheets')).fetchone()
        if already and already['status']=='succeeded':
            return {'ticket_id':public_id,'sync_status':'succeeded','event_state':'completed'}
        t=now()
        db.execute('''INSERT INTO external_syncs
            (id,ticket_id,provider,external_key,status,attempts,last_error,updated_at)
            VALUES (?,?,'google_sheets',?,?,1,?,?)
            ON CONFLICT(ticket_id,provider) DO UPDATE SET status=excluded.status,
            attempts=external_syncs.attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at''',
            (identity(),e['ticket_id'],public_id,status,error_code,t))
        db.execute('UPDATE tickets SET sync_status=?,updated_at=? WHERE id=?',(status,t,e['ticket_id']))
        if status=='succeeded' or failure_stage=='analysis':
            state='completed'
            db.execute('''UPDATE outbox_events SET state='completed',last_error=?,
                delivered_at=COALESCE(delivered_at,?) WHERE event_id=?''',(error_code,t,event_id))
        else:
            row=db.execute('SELECT attempts FROM outbox_events WHERE event_id=?',(event_id,)).fetchone()
            state='dead_letter' if row['attempts']>=4 else 'retry'
            retry_at=(datetime.now(timezone.utc)+timedelta(seconds=30*max(row['attempts'],1))).isoformat()
            db.execute('''UPDATE outbox_events SET state=?,next_attempt_at=?,last_error=? WHERE event_id=?''',
                       (state,retry_at,error_code or 'SYNC_FAILED',event_id))
        return {'ticket_id':public_id,'sync_status':status,'event_state':state}


def change_status(path,public_id,req):
    with session(path,write=True) as db:
        ticket=db.execute('SELECT * FROM tickets WHERE public_id=?',(public_id,)).fetchone()
        if not ticket:
            raise DomainError('TICKET_NOT_FOUND',404)
        allowed = {
            'created': {'in_progress'}, 'processing': {'in_progress'},
            'triaged':{'in_progress'},'awaiting_review':{'in_progress'},
            'in_progress':{'resolved'},'resolved':{'closed'},'closed':set(),
        }
        if req.status not in allowed[ticket['ticket_status']]:
            raise DomainError('INVALID_STATUS_TRANSITION')
        notes=(req.resolution_notes or ticket['resolution_notes'] or '').strip()
        if req.status=='resolved' and len(notes)<8:
            raise DomainError('RESOLUTION_NOTES_REQUIRED',422)
        resolved_at=now() if req.status=='resolved' else ticket['resolved_at']
        closed_at=now() if req.status=='closed' else ticket['closed_at']
        db.execute('''UPDATE tickets SET ticket_status=?,resolution_notes=?,resolved_at=?,
          closed_at=?,updated_at=? WHERE id=?''',
          (req.status,notes or None,resolved_at,closed_at,now(),ticket['id']))
        status_event(db,ticket['id'],ticket['ticket_status'],req.status,'attendant',req.reason)
    return {'ticket_id':public_id,'ticket_status':req.status}


def review_priority(path, public_id, req):
    """Revisão humana explícita e auditável, sem alterar a sugestão original da IA."""
    with session(path,write=True) as db:
        ticket=db.execute('SELECT * FROM tickets WHERE public_id=?',(public_id,)).fetchone()
        if not ticket:
            raise DomainError('TICKET_NOT_FOUND',404)
        if ticket['ticket_status'] in ('resolved','closed'):
            raise DomainError('TICKET_ALREADY_RESOLVED')
        if ticket['analysis_status']=='running':
            raise DomainError('ANALYSIS_IN_PROGRESS')
        if req.priority=='critical' and ticket['impact_scope']!='widespread':
            raise DomainError('CRITICAL_REQUIRES_WIDESPREAD_IMPACT',422)
        reason=req.reason.strip()
        if len(reason)<8:
            raise DomainError('REVIEW_REASON_REQUIRED',422)
        previous=ticket['effective_priority']
        db.execute('UPDATE tickets SET effective_priority=?,updated_at=? WHERE id=?',(req.priority,now(),ticket['id']))
        db.execute('''INSERT INTO priority_review_history
          (id,ticket_id,previous_priority,new_priority,actor_type,reason,created_at)
          VALUES (?,?,?,?,'attendant',?,?)''',
          (identity(),ticket['id'],previous,req.priority,reason,now()))
        return {'ticket_id':public_id,'effective_priority':req.priority,'reviewed_by':'attendant'}


def retry_analysis(path,public_id):
    """Nova tentativa após falha: novo event_id e evento transacional de Outbox."""
    with session(path,write=True) as db:
        ticket=db.execute('SELECT * FROM tickets WHERE public_id=?',(public_id,)).fetchone()
        if not ticket:
            raise DomainError('TICKET_NOT_FOUND',404)
        if ticket['ticket_status'] in ('resolved','closed'):
            raise DomainError('TICKET_ALREADY_RESOLVED')
        if ticket['analysis_status']!='failed':
            raise DomainError('RETRY_REQUIRES_FAILED_ANALYSIS')
        pending=db.execute('''SELECT 1 FROM outbox_events WHERE ticket_id=? AND event_type='ticket.analysis_retry'
                               AND state IN ('pending','retry','sent') LIMIT 1''',(ticket['id'],)).fetchone()
        if pending:
            raise DomainError('RETRY_ALREADY_PENDING')
        event_id=identity()
        t=now()
        body={'event_id':event_id,'event_type':'ticket.analysis_retry','ticket_id':public_id}
        db.execute('''INSERT INTO outbox_events
            (event_id,ticket_id,event_type,payload_json,state,next_attempt_at,created_at)
            VALUES (?,?,?,?,'pending',?,?)''',
            (event_id,ticket['id'],'ticket.analysis_retry',json.dumps(body),t,t))
        db.execute("UPDATE tickets SET analysis_status='pending',sync_status='pending',updated_at=? WHERE id=?",(t,ticket['id']))
        return {'ticket_id':public_id,'event_id':event_id,'event_state':'pending'}
