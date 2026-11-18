"""App FastAPI. Endpoints internos acessíveis somente na rede de serviços local."""
import hmac
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import db_path, service_key
from .storage import init_db
from .schemas import TicketCreate, AnalyzeRequest, SyncRequest, StatusChange, PriorityReview
from .services import tickets
from .services.ai import analyze_ticket


def create_app(database=None, analyzer=None, internal_key=None):
    path=database or db_path()
    adapter=analyzer or analyze_ticket
    secret=internal_key if internal_key is not None else service_key()

    @asynccontextmanager
    async def lifespan(app):
        init_db(path)
        yield

    app=FastAPI(title='AI Support Flow',version='0.1.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
                       allow_credentials=False,allow_methods=['GET','POST','PATCH'],
                       allow_headers=['Content-Type','X-Demo-Role'])

    @app.exception_handler(tickets.DomainError)
    async def domain_error(request,exc):
        return JSONResponse(status_code=exc.http_status,content={'error_code':exc.code})

    def service_auth(x_service_key: str | None=Header(default=None)):
        if not secret or not x_service_key or not hmac.compare_digest(secret,x_service_key):
            raise HTTPException(status_code=401,detail={'error_code':'UNAUTHORIZED_SERVICE'})

    @app.get('/health')
    def health():
        return {'status':'ok'}

    @app.post('/tickets',status_code=201)
    def create(req:TicketCreate):
        return tickets.create_ticket(path,req)

    @app.get('/tickets')
    def list_all():
        return tickets.list_tickets(path)

    @app.get('/tickets/{ticket_id}')
    def detail(ticket_id:str):
        return tickets.get_ticket(path,ticket_id)

    @app.patch('/tickets/{ticket_id}/status')
    def move(ticket_id:str,req:StatusChange,x_demo_role: str | None=Header(default=None)):
        # Somente local: header é SIMULAÇÃO e pode ser forjado; não expor publicamente.
        if x_demo_role!='attendant':
            raise HTTPException(status_code=403,detail={'error_code':'DEMO_ATTENDANT_REQUIRED'})
        return tickets.change_status(path,ticket_id,req)

    @app.patch('/tickets/{ticket_id}/priority')
    def review_priority(ticket_id:str,req:PriorityReview,x_demo_role: str | None=Header(default=None)):
        if x_demo_role!='attendant':
            raise HTTPException(status_code=403,detail={'error_code':'DEMO_ATTENDANT_REQUIRED'})
        return tickets.review_priority(path,ticket_id,req)

    @app.post('/tickets/{ticket_id}/retry-analysis',status_code=202)
    def retry_analysis(ticket_id:str,x_demo_role: str | None=Header(default=None)):
        if x_demo_role!='attendant':
            raise HTTPException(status_code=403,detail={'error_code':'DEMO_ATTENDANT_REQUIRED'})
        return tickets.retry_analysis(path,ticket_id)

    @app.post('/internal/tickets/{ticket_id}/analyze',dependencies=[Depends(service_auth)])
    def analyze(ticket_id:str,req:AnalyzeRequest):
        return tickets.analyze(path,ticket_id,req.event_id,adapter,'test-adapter' if analyzer else (os.getenv('OPENAI_MODEL','gpt-4o-mini') if os.getenv('AI_MODE','mock')=='openai' else 'mock'))

    @app.post('/internal/tickets/{ticket_id}/sync-status',dependencies=[Depends(service_auth)])
    def sync(ticket_id:str,req:SyncRequest):
        return tickets.sync_result(path,ticket_id,req.event_id,req.status,req.failure_stage,req.error_code)

    return app


app=create_app()
