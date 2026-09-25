"""Данные о вошедшем сотруднике для каждого шаблона."""


def current_user(request) -> dict:
    """employee_name, role_name, warehouse_title и perms для шапки и кнопок."""
    actor = getattr(request, 'actor', None)
    if actor is None:
        return {'perms': frozenset()}
    return {
        'employee_name': request.session.get('employee_name', ''),
        'role_name': actor.role_name,
        'warehouse_title': request.session.get('warehouse_title', ''),
        'perms': actor.permissions,
    }
