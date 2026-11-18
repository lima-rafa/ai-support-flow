import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertCircle, ArrowDownRight, ArrowLeft, ArrowRight, Bell, Check,
  CheckCircle2, ChevronDown, ChevronRight, CircleHelp, Clock3, Cloud,
  FileClock, Filter, Headphones, LayoutDashboard, ListFilter, LoaderCircle,
  LockKeyhole, Plus, RefreshCw, RotateCcw, Search, Send, Settings2,
  ShieldAlert, ShieldCheck, Sparkles, Ticket, UserRound, Wifi, X,
} from 'lucide-react'
import { api, describeError } from './api'

const STATUSES = {
  created: 'Criado', processing: 'Processando', triaged: 'Triado',
  awaiting_review: 'Aguardando revisão', in_progress: 'Em atendimento',
  resolved: 'Resolvido', closed: 'Encerrado',
}
const PRIORITIES = { low: 'Baixa', medium: 'Média', high: 'Alta', critical: 'Crítica' }
const CATEGORIES = { network: 'Rede', hardware: 'Hardware', software: 'Software', access: 'Acesso', email: 'E-mail', other: 'Outros' }
const ANALYSIS = { pending: 'Pendente', running: 'Em processamento', succeeded: 'Concluída', failed: 'Falhou' }
const SYNC = { pending: 'Pendente', succeeded: 'Sincronizado', failed: 'Falhou' }
const SCOPE = { unknown: 'Não informado', individual: 'Uma pessoa', partial: 'Parte da equipe', blocked: 'Atividade bloqueada', multiple: 'Várias pessoas', widespread: 'Impacto generalizado' }
const DATE = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
const dateLabel = (value) => value ? DATE.format(new Date(value)) : '—'
const safe = (value, fallback = '—') => value === null || value === undefined || value === '' ? fallback : String(value)

function Pill({ value, type = 'status' }) {
  const names = type === 'priority' ? PRIORITIES : type === 'analysis' ? ANALYSIS : type === 'sync' ? SYNC : STATUSES
  return <span className={`pill pill-${type}-${value || 'unknown'}`}><span className="pill-dot" />{names[value] || safe(value, 'Não definida')}</span>
}

function Notice({ message, onDismiss }) {
  if (!message) return null
  return <div role="alert" className={`notice notice-${message.type || 'info'}`}>
    {message.type === 'success' ? <CheckCircle2 size={19} /> : <AlertCircle size={19} />}
    <span>{message.text}</span>
    <button className="icon-button" aria-label="Fechar aviso" onClick={onDismiss}><X size={16} /></button>
  </div>
}

function Dialog({ title, subtitle, children, onClose, width = 'normal' }) {
  useEffect(() => {
    const handler = (event) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <section role="dialog" aria-modal="true" aria-label={title} className={`modal modal-${width}`}>
      <header className="modal-top"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button onClick={onClose} className="icon-button" aria-label="Fechar janela"><X size={20} /></button></header>
      {children}
    </section>
  </div>
}

function NewTicket({ onClose, onCreate }) {
  const [form, setForm] = useState({ title: '', description: '', affected_service: '', reported_impact: '', impact_scope: 'unknown' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const update = (key, value) => setForm((p) => ({ ...p, [key]: value }))
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true); setError('')
    try { await onCreate({ ...form, affected_service: form.affected_service.trim() || null, reported_impact: form.reported_impact.trim() || null }) }
    catch (err) { setError(describeError(err)); setSaving(false) }
  }
  return <Dialog title="Abrir novo chamado" subtitle="Descreva a situação. A triagem será iniciada automaticamente." onClose={onClose} width="wide">
    <form onSubmit={submit} className="modal-body form-stack">
      {error && <div className="form-error"><AlertCircle size={16}/>{error}</div>}
      <label>Título do chamado <span>*</span><input required minLength={4} maxLength={150} value={form.title} onChange={(e) => update('title', e.target.value)} placeholder="Ex.: Não consigo acessar o e-mail corporativo" autoFocus /></label>
      <label>Descrição do problema <span>*</span><textarea required minLength={10} maxLength={5000} rows={5} value={form.description} onChange={(e) => update('description', e.target.value)} placeholder="Explique o que acontece, quando começou e quais atividades foram afetadas." /></label>
      <div className="form-grid">
        <label>Serviço afetado<input maxLength={100} value={form.affected_service} onChange={(e) => update('affected_service', e.target.value)} placeholder="Ex.: e-mail, VPN, sistema" /></label>
        <label>Abrangência<select value={form.impact_scope} onChange={(e) => update('impact_scope', e.target.value)}>{Object.entries(SCOPE).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
      </div>
      <label>Impacto relatado<input maxLength={1000} value={form.reported_impact} onChange={(e) => update('reported_impact', e.target.value)} placeholder="Ex.: Não consigo realizar minhas atividades" /></label>
      <div className="form-hint"><Sparkles size={17}/>A análise da IA é uma sugestão e pode exigir revisão humana. Não inclua senhas ou dados pessoais reais.</div>
      <div className="modal-actions"><button className="button secondary" type="button" onClick={onClose} disabled={saving}>Cancelar</button><button className="button primary" type="submit" disabled={saving}>{saving ? <LoaderCircle className="spin" size={17}/> : <Plus size={17}/>} {saving ? 'Criando...' : 'Criar chamado'}</button></div>
    </form>
  </Dialog>
}

function ReviewPriority({ ticket, onClose, onSubmit }) {
  const [priority, setPriority] = useState(ticket.effective_priority || 'medium')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault(); setSaving(true); setError('')
    try { await onSubmit({ priority, reason }) } catch (err) { setError(describeError(err)); setSaving(false) }
  }
  return <Dialog title="Revisar prioridade" subtitle={`Decisão humana auditável para ${ticket.public_id}`} onClose={onClose}>
    <form className="modal-body form-stack" onSubmit={submit}>
      {error && <div className="form-error">{error}</div>}
      <div className="comparison"><div><small>Sugestão da IA</small><Pill type="priority" value={ticket.analysis?.suggested_priority}/></div><ArrowRight size={18}/><div><small>Prioridade atual</small><Pill type="priority" value={ticket.effective_priority}/></div></div>
      <label>Nova prioridade<select value={priority} onChange={(e)=>setPriority(e.target.value)}>{Object.entries(PRIORITIES).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
      <label>Justificativa <span>*</span><textarea required minLength={8} maxLength={300} rows={3} value={reason} onChange={(e)=>setReason(e.target.value)} placeholder="Explique o motivo técnico e a evidência da revisão" /></label>
      {priority === 'critical' && ticket.impact_scope !== 'widespread' && <div className="form-error">Prioridade crítica exige abrangência generalizada declarada ao criar o chamado.</div>}
      <div className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>Cancelar</button><button type="submit" className="button primary" disabled={saving || (priority === 'critical' && ticket.impact_scope !== 'widespread')}>{saving ? 'Salvando...' : 'Registrar revisão'}</button></div>
    </form>
  </Dialog>
}

function StatusUpdate({ ticket, next, onClose, onSubmit }) {
  const [notes, setNotes] = useState(ticket.resolution_notes || '')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const copy = { in_progress: 'Assumir atendimento', resolved: 'Registrar resolução', closed: 'Encerrar chamado' }
  const submit = async (e) => {
    e.preventDefault(); setSaving(true); setError('')
    try { await onSubmit({ status: next, ...(next === 'resolved' ? { resolution_notes: notes } : {}), reason: reason.trim() || null }) }
    catch (err) { setError(describeError(err)); setSaving(false) }
  }
  return <Dialog title={copy[next]} subtitle={`${ticket.public_id} · ${safe(ticket.title)}`} onClose={onClose}>
    <form onSubmit={submit} className="modal-body form-stack">
      {error && <div className="form-error">{error}</div>}
      {next === 'resolved' && <label>Descrição da solução <span>*</span><textarea autoFocus required minLength={8} maxLength={2000} rows={4} value={notes} onChange={(e)=>setNotes(e.target.value)} placeholder="Descreva quais ações foram realizadas para resolver o problema." /></label>}
      {next === 'closed' && <p className="confirm-copy">O chamado será encerrado. Esta ação não pode ser revertida pelo fluxo atual.</p>}
      <label>Motivo / observação (opcional)<input maxLength={300} value={reason} onChange={(e)=>setReason(e.target.value)} placeholder="Ex.: Solução validada com o solicitante" /></label>
      <div className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>Cancelar</button><button disabled={saving} type="submit" className="button primary">{saving ? 'Salvando...' : copy[next]}</button></div>
    </form>
  </Dialog>
}

function Metric({ label, count, change, icon: Icon, tone }) {
  return <div className="metric"><div className={`metric-icon ${tone}`}><Icon size={20}/></div><div className="metric-name">{label}</div><div className="metric-value">{count}</div><div className="metric-footer">{change}</div></div>
}

function TicketTable({ tickets, onOpen, loading }) {
  return <div className="table-scroll"><table><thead><tr><th>CHAMADO</th><th>STATUS</th><th>PRIORIDADE</th><th>ANÁLISE</th><th>ABERTO EM</th><th aria-label="Abrir" /></tr></thead><tbody>
    {tickets.map((t) => <tr key={t.ticket_id} onClick={() => onOpen(t.ticket_id)} tabIndex={0} onKeyDown={(e)=> { if(e.key === 'Enter') onOpen(t.ticket_id) }}>
      <td><strong className="ticket-id">{t.ticket_id}</strong><span className="ticket-title">{t.title}</span></td>
      <td><Pill value={t.ticket_status}/></td><td><Pill type="priority" value={t.effective_priority}/></td><td><Pill type="analysis" value={t.analysis_status}/></td><td className="date-cell">{dateLabel(t.created_at)}</td><td><ChevronRight size={18} className="arrow-cell"/></td>
    </tr>)}
    {!tickets.length && <tr><td className="empty-table" colSpan={6}>{loading ? 'Carregando chamados...' : 'Nenhum chamado corresponde aos filtros.'}</td></tr>}
  </tbody></table></div>
}

function TicketDetail({ ticket, loading, attendant, onBack, onReview, onMove, onRetry }) {
  if (loading && !ticket) return <div className="loading-box"><LoaderCircle className="spin"/>Carregando detalhes...</div>
  if (!ticket) return null
  const a = ticket.analysis
  const status = ticket.ticket_status
  const canReview = attendant && !['resolved','closed'].includes(status) && ticket.analysis_status !== 'running'
  const nextStatus = ['created','processing','triaged','awaiting_review'].includes(status) ? 'in_progress' : status === 'in_progress' ? 'resolved' : status === 'resolved' ? 'closed' : null
  const nextLabel = { in_progress: 'Assumir atendimento', resolved: 'Resolver chamado', closed: 'Encerrar chamado' }
  return <>
    <button className="back-link" onClick={onBack}><ArrowLeft size={17}/> Voltar para chamados</button>
    <div className="detail-header"><div><div className="eyebrow">DETALHES DO CHAMADO <span className="separator">/</span> {ticket.public_id}</div><h1>{ticket.title}</h1><div className="detail-meta"><Pill value={status}/><Pill type="priority" value={ticket.effective_priority}/><span><Clock3 size={15}/> Criado em {dateLabel(ticket.created_at)}</span></div></div><div className="detail-actions">{attendant && nextStatus && <button className="button primary" onClick={()=>onMove(nextStatus)}>{nextLabel[nextStatus]} <ArrowRight size={17}/></button>}</div></div>
    <div className="detail-grid"><div className="detail-main">
      <section className="panel detail-section"><h2><Ticket size={19}/> Informações do chamado</h2><p className="description-text">{ticket.description}</p><div className="info-grid"><div><small>Serviço afetado</small><strong>{safe(ticket.affected_service)}</strong></div><div><small>Abrangência</small><strong>{SCOPE[ticket.impact_scope] || safe(ticket.impact_scope)}</strong></div><div><small>Impacto relatado</small><strong>{safe(ticket.reported_impact)}</strong></div><div><small>Sincronização Sheets</small><Pill type="sync" value={ticket.sync_status}/></div></div></section>
      <section className="panel detail-section ai-section"><div className="section-title-row"><h2><span className="ai-icon"><Sparkles size={18}/></span> Análise inteligente</h2><Pill type="analysis" value={ticket.analysis_status}/></div>
        {a?.status === 'succeeded' ? <>
          <div className="ai-summary-label">RESUMO GERADO PELA IA</div><p className="ai-summary">{a.summary}</p>
          <div className="ai-info"><div><small>Categoria identificada</small><strong>{CATEGORIES[a.category] || safe(a.category)}</strong></div><div><small>Prioridade sugerida</small><Pill type="priority" value={a.suggested_priority}/></div><div><small>Revisão humana</small><strong>{a.requires_human_review ? 'Necessária' : 'Não obrigatória'}</strong></div></div>
          {a.review_reason && <div className="review-reason"><ShieldAlert size={18}/><div><strong>Justificativa para revisão</strong><p>{a.review_reason}</p></div></div>}
          <h3>Recomendações</h3><ul className="recommendations">{(a.recommendations || []).map((item,i)=><li key={i}><span>{i+1}</span><p>{item}</p></li>)}</ul>
        </> : <div className="analysis-placeholder"><span className="placeholder-icon">{ticket.analysis_status === 'failed' ? <AlertCircle size={24}/> : <LoaderCircle className={ticket.analysis_status === 'running' ? 'spin' : ''} size={24}/>}</span><strong>{ticket.analysis_status === 'failed' ? 'Não foi possível concluir a análise' : 'Aguardando processamento'}</strong><p>{ticket.analysis_status === 'failed' ? `Código: ${safe(a?.error_code, 'ANALYSIS_FAILED')}. O chamado permanece disponível para atendimento.` : 'O n8n está processando este chamado. A página será atualizada automaticamente.'}</p>{ticket.analysis_status === 'failed' && attendant && <button className="button secondary" onClick={onRetry}><RotateCcw size={16}/> Tentar análise novamente</button>}</div>}
        {a && <div className="technical-meta"><span>Modelo solicitado: <b>{safe(a.model_name)}</b></span><span>Modelo retornado: <b>{safe(a.provider_model, 'Não registrado')}</b></span><span>Prompt: <b>{safe(a.prompt_version)}</b></span></div>}
      </section>
      {ticket.resolution_notes && <section className="panel detail-section"><h2><CheckCircle2 size={19}/> Resolução registrada</h2><p className="description-text">{ticket.resolution_notes}</p></section>}
      <section className="panel detail-section"><h2><FileClock size={19}/> Histórico de atividades</h2><div className="timeline">{(ticket.history || []).map((entry, i)=><div className="timeline-item" key={i}><div className="timeline-dot"/><div><strong>{STATUSES[entry.new_status] || entry.new_status}</strong><p>{entry.reason || `Alteração realizada por ${entry.actor_type}`}</p><small>{dateLabel(entry.created_at)} · {entry.actor_type === 'attendant' ? 'Atendente' : 'Sistema'}</small></div></div>)}</div></section>
    </div><aside className="detail-aside">
      <section className="panel side-panel"><h2>Gerenciamento</h2><div className="side-kv"><span>Prioridade atual</span><Pill type="priority" value={ticket.effective_priority}/></div><div className="side-kv"><span>Estado</span><Pill value={status}/></div>{attendant && <button className="button secondary full" onClick={onReview} disabled={!canReview}><Settings2 size={16}/> Revisar prioridade</button>}{!attendant && <p className="side-hint"><LockKeyhole size={14}/> Ative o modo atendente para realizar alterações.</p>}</section>
      {ticket.priority_reviews?.length > 0 && <section className="panel side-panel"><h2>Revisões de prioridade</h2>{ticket.priority_reviews.map((r,i)=><div className="priority-history" key={i}><div><Pill type="priority" value={r.previous_priority}/><ArrowRight size={14}/><Pill type="priority" value={r.new_priority}/></div><p>{r.reason}</p><small>{dateLabel(r.created_at)}</small></div>)}</section>}
      <section className="side-tip"><ShieldCheck size={20}/><div><strong>Fluxo com revisão humana</strong><p>A IA auxilia na triagem. A resolução e o encerramento dependem de uma decisão do atendente.</p></div></section>
    </aside></div>
  </>
}

export default function App() {
  const [tickets, setTickets] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [apiOnline, setApiOnline] = useState(null)
  const [attendant, setAttendant] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [view, setView] = useState('overview')
  const [dialog, setDialog] = useState(null)
  const [notice, setNotice] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const notify = (text, type = 'error') => setNotice({ text, type })
  const refresh = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const data = await api.list()
      setTickets(data)
      setApiOnline(true)
      if (selectedId) {
        try { setSelected(await api.get(selectedId)) }
        catch (err) { if (!silent) notify(describeError(err)) }
      }
    } catch (err) {
      setApiOnline(false)
      if (!silent) notify(describeError(err))
    } finally { setLoading(false); setRefreshing(false); setDetailLoading(false) }
  }, [selectedId])

  useEffect(() => { refresh(true) }, [refresh])
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') refresh(true)
    }, 6000)
    return () => window.clearInterval(id)
  }, [refresh])

  const openTicket = async (id) => {
    setSelectedId(id); setSelected(null); setDetailLoading(true)
    setView('detail'); setNotice(null)
    try { const data = await api.get(id); setSelected(data) }
    catch (err) { notify(describeError(err)) }
    finally { setDetailLoading(false) }
  }
  const perform = async (callback, success) => {
    await callback()
    setDialog(null); notify(success, 'success')
    await refresh(true)
  }
  const createTicket = async (payload) => {
    const response = await api.create(payload)
    setDialog(null)
    notify(`Chamado ${response.ticket_id} criado. A análise será processada em segundo plano pelo fluxo existente.`, 'success')
    await refresh(true)
    await openTicket(response.ticket_id)
  }

  const stats = useMemo(() => ({
    total: tickets.length,
    active: tickets.filter((t) => !['closed','resolved'].includes(t.ticket_status)).length,
    reviewing: tickets.filter((t) => t.ticket_status === 'awaiting_review').length,
    resolved: tickets.filter((t) => ['resolved','closed'].includes(t.ticket_status)).length,
  }), [tickets])
  const filtered = useMemo(() => tickets.filter((t) => {
    const matchesText = `${t.ticket_id} ${t.title}`.toLowerCase().includes(query.toLowerCase())
    const matchesStatus = statusFilter === 'all' || (statusFilter === 'active' ? !['resolved','closed'].includes(t.ticket_status) : statusFilter === 'finished' ? ['resolved','closed'].includes(t.ticket_status) : t.ticket_status === statusFilter)
    return matchesText && matchesStatus && (priorityFilter === 'all' || t.effective_priority === priorityFilter)
  }), [tickets, query, statusFilter, priorityFilter])

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Activity size={23} strokeWidth={2.8}/></span><span>AI Support<span className="brand-accent">Flow</span><small>GESTÃO INTELIGENTE DE SUPORTE</small></span></div>
      <div className="nav-label">MENU PRINCIPAL</div>
      <nav aria-label="Menu principal">
        <button className={`nav-item ${view === 'overview' ? 'active' : ''}`} onClick={()=>{setView('overview');setSelectedId(null);setSelected(null);setStatusFilter('all')}}><LayoutDashboard size={19}/> Visão geral</button>
        <button className={`nav-item ${view === 'tickets' || view === 'detail' ? 'active' : ''}`} onClick={()=>{setView('tickets');setSelectedId(null);setSelected(null);setStatusFilter('all')}}><Ticket size={19}/> Chamados <span className="nav-count">{tickets.length}</span></button>
        <button className="nav-item" onClick={()=>{setView('tickets');setSelectedId(null);setSelected(null);setStatusFilter('awaiting_review')}}><ShieldCheck size={19}/> Revisão pendente {stats.reviewing>0 && <span className="nav-count attention">{stats.reviewing}</span>}</button>
      </nav>
      <div className="sidebar-bottom"><div className="sidebar-help"><Sparkles size={19}/><strong>Assistência com IA</strong><p>Triagem automática, histórico rastreável e decisão humana.</p></div><div className="sidebar-profile"><span className="avatar"><UserRound size={18}/></span><div><strong>{attendant ? 'Atendente (demo)' : 'Visualizador'}</strong><small>Ambiente local</small></div><ChevronDown size={15}/></div></div>
    </aside>
    <div className="main-area"><header className="topbar"><div className="breadcrumbs">Workspace <ChevronRight size={14}/> <span>{view === 'detail' ? 'Detalhes do chamado' : view === 'tickets' ? 'Chamados' : 'Visão geral'}</span></div><div className="topbar-actions"><span className={`connection ${apiOnline ? 'online' : 'offline'}`}><span/> {apiOnline === null ? 'Conectando' : apiOnline ? 'API conectada' : 'API indisponível'}</span><label className="role-switch"><span>Modo atendente</span><input type="checkbox" checked={attendant} onChange={(e)=>setAttendant(e.target.checked)}/><i/></label><div className="top-avatar"><UserRound size={18}/></div></div></header>
      <main className="content"><Notice message={notice} onDismiss={()=>setNotice(null)}/>
        {view === 'detail' ? <TicketDetail ticket={selected} loading={detailLoading} attendant={attendant} onBack={()=>{setView('tickets');setSelectedId(null);setSelected(null)}} onReview={()=>setDialog('review')} onMove={(next)=>setDialog(next)} onRetry={()=>setDialog('retry')}/> : <>
        <div className="page-header"><div><div className="eyebrow">CENTRAL DE ATENDIMENTO <span className="eyebrow-line"/></div><h1>{view === 'overview' ? 'Visão geral' : 'Todos os chamados'}</h1><p>Acompanhe solicitações e análises inteligentes em um só lugar.</p></div><button className="button primary create-button" onClick={()=>setDialog('new')}><Plus size={18}/> Novo chamado</button></div>
        {view === 'overview' && <><div className="metrics-grid"><Metric icon={Ticket} label="Total de chamados" count={stats.total} change="Registros disponíveis" tone="blue"/><Metric icon={Activity} label="Em andamento" count={stats.active} change="Ainda não concluídos" tone="indigo"/><Metric icon={ShieldAlert} label="Aguardando revisão" count={stats.reviewing} change="Ação humana necessária" tone="amber"/><Metric icon={CheckCircle2} label="Resolvidos" count={stats.resolved} change="Resolvidos ou encerrados" tone="green"/></div><div className="section-head"><div><h2>Chamados recentes</h2><p>Últimas solicitações registradas no sistema</p></div><button className="text-button" onClick={()=>setView('tickets')}>Ver todos <ArrowRight size={16}/></button></div></>}
        <section className="panel table-panel"><div className="table-toolbar"><div className="toolbar-left"><h2>{view === 'overview' ? 'Últimas solicitações' : 'Gerenciar solicitações'}</h2><span className="count-label">{filtered.length} registros</span></div><div className="toolbar-right"><div className="search-box"><Search size={17}/><input aria-label="Buscar chamados" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Buscar chamado..."/></div><div className="select-wrap"><ListFilter size={16}/><select aria-label="Filtrar por status" value={statusFilter} onChange={(e)=>setStatusFilter(e.target.value)}><option value="all">Todos os status</option><option value="active">Em aberto</option><option value="awaiting_review">Aguardando revisão</option><option value="in_progress">Em atendimento</option><option value="finished">Concluídos</option></select></div><div className="select-wrap priority-select"><Filter size={16}/><select aria-label="Filtrar por prioridade" value={priorityFilter} onChange={(e)=>setPriorityFilter(e.target.value)}><option value="all">Prioridades</option>{Object.entries(PRIORITIES).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></div><button title="Atualizar dados" aria-label="Atualizar dados" className="refresh-button" onClick={()=>refresh(false)} disabled={refreshing}><RefreshCw className={refreshing ? 'spin' : ''} size={17}/></button></div></div><TicketTable tickets={view === 'overview' ? filtered.slice(0,8) : filtered} onOpen={openTicket} loading={loading}/><div className="table-footer"><span>Atualização automática a cada 6 segundos · máximo de 100 registros retornados pela API</span><span>AI Support Flow MVP</span></div></section>
        {view === 'overview' && <div className="bottom-grid"><div className="info-banner"><div className="banner-art"><Sparkles size={28}/></div><div><h3>Inteligência aplicada ao suporte</h3><p>Classifique solicitações, receba recomendações e preserve a decisão final do atendente.</p></div><button onClick={()=>setView('tickets')} className="banner-link">Explorar chamados <ArrowRight size={16}/></button></div><div className="demo-card"><ShieldCheck size={20}/><div><h3>Ambiente demonstrativo</h3><p>Não use informações sensíveis. O modo atendente é uma simulação, sem autenticação real.</p></div></div></div>}
        </>}
      </main>
      <footer className="footer">© AI Support Flow · Protótipo local de portfólio <span>React + FastAPI + n8n + Google Sheets</span></footer>
    </div>
    {dialog === 'new' && <NewTicket onClose={()=>setDialog(null)} onCreate={createTicket}/>}
    {dialog === 'review' && selected && <ReviewPriority ticket={selected} onClose={()=>setDialog(null)} onSubmit={(payload)=>perform(()=>api.reviewPriority(selected.public_id,payload),'Prioridade revisada com justificativa registrada.')}/>}
    {['in_progress','resolved','closed'].includes(dialog) && selected && <StatusUpdate ticket={selected} next={dialog} onClose={()=>setDialog(null)} onSubmit={(payload)=>perform(()=>api.moveStatus(selected.public_id,payload),'Estado do chamado atualizado.')}/>}
    {dialog === 'retry' && selected && <Dialog title="Tentar análise novamente" subtitle={selected.public_id} onClose={()=>setDialog(null)}><div className="modal-body"><p>Uma nova tentativa será colocada na Outbox e processada pelo n8n. Isso pode gerar uma nova chamada à OpenAI.</p><div className="modal-actions"><button className="button secondary" onClick={()=>setDialog(null)}>Cancelar</button><button className="button primary" onClick={async()=>{try{await perform(()=>api.retry(selected.public_id),'Nova análise solicitada.')}catch(e){notify(describeError(e));setDialog(null)}}}>Solicitar nova análise</button></div></div></Dialog>}
  </div>
}
