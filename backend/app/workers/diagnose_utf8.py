"""Read-only UTF-8 diagnostic for a ticket. Usage: python -m app.workers.diagnose_utf8 TCK-0005"""
import json
import os
import sys
from urllib.request import urlopen
from ..config import db_path
from ..storage import session


def diagnose(public_id):
    with session(db_path()) as conn:
        ticket=conn.execute('SELECT id,title,description FROM tickets WHERE public_id=?',(public_id,)).fetchone()
        if not ticket:
            print('Ticket not found:',public_id)
            return 2
        analysis=conn.execute('''SELECT summary,review_reason,recommendations_json,model_name,provider_model
         FROM analysis_results WHERE ticket_id=? ORDER BY attempt_number DESC LIMIT 1''',(ticket['id'],)).fetchone()
        fields={'ticket.title':ticket['title'],'ticket.description':ticket['description']}
        if analysis:
            fields.update({'analysis.summary':analysis['summary'],
                           'analysis.review_reason':analysis['review_reason'],
                           'analysis.recommendations_json':analysis['recommendations_json']})
        print('SQLite read-only UTF8 check:',public_id)
        for key,value in fields.items():
            if value is None:
                print(key,'= empty')
                continue
            suspicious=any(marker in value for marker in ('Ã£','Ã¡','Ã©','Ãª','Ã§','Ã³','Ã­','Ãº','Â','\ufffd'))
            print(key,'=', 'POSSIBLE_MOJIBAKE' if suspicious else 'NO_MOJIBAKE_MARKERS',
                  '; non_ascii_chars=',sum(ord(ch)>127 for ch in value))
        if analysis:
            print('configured_model=',analysis['model_name'])
            print('provider_reported_model=',analysis['provider_model'] or '(not recorded for old runs)')
    try:
        with urlopen('http://127.0.0.1:8000/tickets/'+public_id, timeout=3) as r:
            payload=json.load(r)
        response_text=json.dumps(payload.get('analysis',{}),ensure_ascii=False)
        print('API read-only UTF8 check:',
              'POSSIBLE_MOJIBAKE' if any(x in response_text for x in ('Ã£','Ã¡','Ã©','Ã§','\ufffd'))
              else 'NO_MOJIBAKE_MARKERS')
    except Exception as exc:
        print('API check skipped:',type(exc).__name__)
    return 0


if __name__=='__main__':
    sys.exit(diagnose(sys.argv[1] if len(sys.argv)>1 else 'TCK-0005'))
