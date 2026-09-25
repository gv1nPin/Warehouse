"""Общие куски для page-views: логирование BLL, layout главной, eid."""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from warehouse.common import PermissionName

from ..controller_logging import dto_preview, log_bll_call, log_bll_error, log_bll_ok


def eid(request: HttpRequest) -> int:
    """employee_id из JWT-payload (request.actor)."""
    return request.actor.employee_id


def perms(request: HttpRequest) -> frozenset[str]:
    return getattr(request.actor, "permissions", frozenset()) or frozenset()


def has_perm(request: HttpRequest, permission: PermissionName | str) -> bool:
    name = permission.value if isinstance(permission, PermissionName) else permission
    return name in perms(request)


def home_layout(request: HttpRequest) -> dict[str, list[str]]:
    """Счётчики и плитки по permissions из БД (не по имени роли)."""
    p = perms(request)

    def has(perm: PermissionName) -> bool:
        return perm.value in p

    def uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    warehouse = any(
        has(x)
        for x in (
            PermissionName.SHIPMENT_CREATE,
            PermissionName.SHIPMENT_DISPATCH,
            PermissionName.SHIPMENT_ACCEPT,
            PermissionName.SHIPMENT_CANCEL,
            PermissionName.SHIPMENT_VIEW_ALL,
        )
    )

    if not warehouse and not has(PermissionName.EMPLOYEE_MANAGE):
        return {"counters": ["trips"], "main": ["trips"], "extra": []}

    counters: list[str] = []
    main: list[str] = []
    extra: list[str] = ["stock", "docs"]

    if has(PermissionName.SHIPMENT_CREATE):
        counters.append("draft")
        main.append("create")
    if has(PermissionName.SHIPMENT_DISPATCH):
        counters.append("reserved")
    if has(PermissionName.SHIPMENT_ACCEPT):
        counters.append("incoming")
        main.append("receipt")
    if has(PermissionName.SHIPMENT_CREATE) or has(PermissionName.SHIPMENT_CANCEL) or has(
        PermissionName.SHIPMENT_VIEW_ALL
    ):
        counters.append("discrepancy")

    main.append("shipments")

    if has(PermissionName.EMPLOYEE_MANAGE):
        for c in ("draft", "reserved", "incoming", "discrepancy"):
            if c not in counters:
                counters.append(c)
        if "create" not in main:
            main.insert(0, "create")
        if has(PermissionName.SHIPMENT_ACCEPT) and "receipt" not in main:
            main.append("receipt")
        extra.extend(["employees", "refs"])

    return {"counters": uniq(counters), "main": uniq(main), "extra": uniq(extra)}


def bll_call(op: str, request: HttpRequest, **payload: Any) -> None:
    log_bll_call(op, employee_id=getattr(request.actor, "employee_id", None), **payload)


def bll_ok(op: str, result: Any = None, **extra: Any) -> None:
    log_bll_ok(op, dto_preview(result) if result is not None else None, **extra)


def bll_err(op: str, request: HttpRequest, exc: BaseException) -> None:
    log_bll_error(op, exc, employee_id=getattr(request.actor, "employee_id", None))
