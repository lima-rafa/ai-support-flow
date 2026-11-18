"""Priorização determinística: nunca confirma prioridade crítica automaticamente."""
PRIORITY_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def apply_rules(analysis, impact_scope):
    declared_floor = {
        'unknown': 'low', 'individual': 'low', 'partial': 'medium',
        'blocked': 'high', 'multiple': 'high', 'widespread': 'high',
    }[impact_scope]
    suggested = analysis.suggested_priority
    bounded = 'high' if suggested == 'critical' else suggested
    effective = max((declared_floor, bounded), key=PRIORITY_ORDER.__getitem__)
    human = suggested == 'critical' or impact_scope in ('blocked', 'multiple', 'widespread')
    reason = analysis.review_reason
    if suggested == 'critical':
        reason = 'Prioridade crítica sugerida: confirmação humana obrigatória. ' + reason
    elif impact_scope in ('blocked','multiple','widespread'):
        reason = 'Impacto declarado significativo: revisão humana necessária. ' + reason
    elif impact_scope == 'unknown':
        human = True
        reason = 'Impacto não determinado: revisão humana necessária. ' + reason
    return effective, human, reason[:300]
