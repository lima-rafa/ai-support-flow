const ERROR_TRANSLATIONS = {
  TICKET_NOT_FOUND: 'Chamado não encontrado.',
  INVALID_STATUS_TRANSITION: 'Essa mudança de status não é permitida.',
  RESOLUTION_NOTES_REQUIRED: 'Informe uma resolução com pelo menos 8 caracteres.',
  CRITICAL_REQUIRES_WIDESPREAD_IMPACT: 'Prioridade crítica exige abrangência generalizada informada na criação.',
  ANALYSIS_IN_PROGRESS: 'A análise está em andamento. Aguarde antes de revisar.',
  RETRY_REQUIRES_FAILED_ANALYSIS: 'Só é possível tentar novamente quando a análise falhou.',
  RETRY_ALREADY_PENDING: 'Já existe uma nova tentativa pendente.',
  TICKET_ALREADY_RESOLVED: 'Este chamado já foi resolvido ou encerrado.',
  REVIEW_REASON_REQUIRED: 'Informe a justificativa da revisão.',
  DEMO_ATTENDANT_REQUIRED: 'Ative o modo atendente para esta ação.',
}

export function describeError(error) {
  const code = error?.error_code || error?.detail?.error_code
  return ERROR_TRANSLATIONS[code] || (code ? `Falha: ${code}` : error?.message || 'Não foi possível completar a operação.')
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    })
  } catch (cause) {
    throw new Error('Não foi possível acessar a API. Verifique o backend em 127.0.0.1:8000.', { cause })
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`)
    error.status = response.status
    error.error_code = data?.error_code || data?.detail?.error_code
    error.detail = data?.detail
    error.validation = Array.isArray(data?.detail) ? data.detail : null
    throw error
  }
  return data
}

const attendantHeaders = { 'X-Demo-Role': 'attendant' }

export const api = {
  health: () => request('/health'),
  list: () => request('/tickets'),
  get: (id) => request(`/tickets/${encodeURIComponent(id)}`),
  create: (payload) => request('/tickets', { method: 'POST', body: JSON.stringify(payload) }),
  reviewPriority: (id, payload) => request(`/tickets/${encodeURIComponent(id)}/priority`, {
    method: 'PATCH', headers: attendantHeaders, body: JSON.stringify(payload),
  }),
  moveStatus: (id, payload) => request(`/tickets/${encodeURIComponent(id)}/status`, {
    method: 'PATCH', headers: attendantHeaders, body: JSON.stringify(payload),
  }),
  retry: (id) => request(`/tickets/${encodeURIComponent(id)}/retry-analysis`, {
    method: 'POST', headers: attendantHeaders,
  }),
}
