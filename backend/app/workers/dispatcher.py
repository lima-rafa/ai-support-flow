"""Dispatcher V1 de instância única com reentrega e reconciliação simples.

Não executa scripts recebidos pelo webhook. O 2xx apenas acusa recebimento.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
import httpx
from ..config import db_path
from ..storage import init_db, session
from ..services.tickets import now


def dispatch_once(path=None, client=None):
    path=path or db_path()
    url=os.getenv('N8N_WEBHOOK_URL','http://n8n:5678/webhook/asf-ticket-created')
    key=os.getenv('N8N_WEBHOOK_KEY','')
    if not key:
        raise RuntimeError('N8N_WEBHOOK_KEY missing: configure .env')
    moment=now()
    with session(path,write=True) as db:
        # Reconcilia entregas sem callback: possível crash do workflow após 2xx.
        deadline=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        db.execute('''UPDATE outbox_events SET state='retry',next_attempt_at=?
                      WHERE state='sent' AND delivered_at < ?''',(moment,deadline))
        e=db.execute('''SELECT * FROM outbox_events
                       WHERE state IN ('pending','retry') AND next_attempt_at<=?
                       ORDER BY created_at LIMIT 1''',(moment,)).fetchone()
        if not e:
            return False
        event_id=e['event_id']
        tries=e['attempts']+1
        db.execute('''UPDATE outbox_events SET state='sent',attempts=?,delivered_at=?,
                      last_error=NULL WHERE event_id=?''',(tries,moment,event_id))
        payload=json.loads(e['payload_json'])
    request=client or httpx.Client(timeout=10.0)
    close=client is None
    try:
        resp=request.post(url,json=payload,headers={'X-N8N-Key':key})
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        with session(path,write=True) as db:
            row=db.execute('SELECT state FROM outbox_events WHERE event_id=?',(event_id,)).fetchone()
            if row and row['state']=='sent':
                next_at=(datetime.now(timezone.utc)+timedelta(seconds=min(30*2**(tries-1),300))).isoformat()
                db.execute('''UPDATE outbox_events SET state=?,next_attempt_at=?,last_error=?
                              WHERE event_id=?''',
                           ('dead_letter' if tries>=4 else 'retry',next_at,'WEBHOOK_DELIVERY_FAILED',event_id))
    finally:
        if close:
            request.close()
    return True


def main():
    path=db_path()
    init_db(path)
    while True:
        try:
            any_work=dispatch_once(path)
            if not any_work:
                time.sleep(3)
        except Exception as err:
            print('Dispatcher error:',type(err).__name__,flush=True)
            time.sleep(5)


if __name__=='__main__':
    main()
