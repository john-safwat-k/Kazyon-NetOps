"""Business logic service for the 1,150+ Branches and 3 Network Providers (ISPs) directory."""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.audit import record_audit_event
from app.common.exceptions import DuplicateResourceError, EntityNotFoundError
from app.directory.models import Branch, NetworkProvider
from app.directory.schemas import (
    BranchCreateRequest,
    BranchListResponse,
    BranchResponse,
    BranchUpdateRequest,
    IspResponse,
    IspUpdateRequest,
)
from app.directory.seeder import (
    ISP_DEFAULTS,
    REGIONAL_IT_DEFAULTS,
    derive_branch_ips,
    ensure_default_isps,
    seed_branches_from_excel,
)

logger = logging.getLogger("it_net.directory.service")


def ensure_directory_seeded(db: Session) -> None:
    """Seed the 3 ISPs and 1,150 branches from `Copy of All store ISP (2).xlsx` if the directory is empty,
    and keep branch `isp_contact_mail` synchronized when an ISP's support email was customized on Page 10."""
    isps_map = ensure_default_isps(db)
    count = db.execute(select(func.count()).select_from(Branch)).scalar_one()
    if count == 0:
        logger.info("Branches table is empty — seeding 1,150 stores from Excel directory...")
        seed_branches_from_excel(db, dry_run=False)

    # Sync any ISP whose support_email was updated on Page 10 across its branches
    synced_any = False
    for isp_key, provider in isps_map.items():
        default_mail = str(ISP_DEFAULTS.get(isp_key, {}).get("support_email", "")).strip()
        current_mail = (provider.support_email or "").strip()
        if current_mail and current_mail != default_mail:
            res = db.execute(
                update(Branch)
                .where(
                    func.upper(Branch.isp_name) == isp_key,
                    Branch.isp_contact_mail == default_mail,
                )
                .values(isp_contact_mail=current_mail)
            )
            if getattr(res, "rowcount", 0):
                synced_any = True
    if synced_any:
        db.commit()


def list_branches(
    db: Session,
    *,
    search: Optional[str] = None,
    region: Optional[str] = None,
    isp_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> BranchListResponse:
    """Return a paginated, filtered list of branches along with region and ISP counts."""
    stmt = select(Branch)
    if search:
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Branch.branch_code).like(q),
                func.lower(Branch.name).like(q),
                func.lower(Branch.ip_1).like(q),
                func.lower(Branch.ip_2).like(q),
                func.lower(func.coalesce(Branch.ll_circuit_id, "")).like(q),
                func.lower(func.coalesce(Branch.backup_circuit_id, "")).like(q),
            )
        )
    if region and region.lower() != "all":
        stmt = stmt.where(func.lower(Branch.region) == region.strip().lower())
    if isp_name and isp_name.upper() != "ALL":
        stmt = stmt.where(func.upper(Branch.isp_name) == isp_name.strip().upper())
    if is_active is not None:
        stmt = stmt.where(Branch.is_active.is_(is_active))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = (
        db.execute(stmt.order_by(Branch.branch_code.asc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )

    reg_rows = db.execute(
        select(Branch.region, func.count(Branch.id)).group_by(Branch.region)
    ).all()
    regions_count = {str(r or "Unknown"): int(c) for r, c in reg_rows}

    isp_rows = db.execute(
        select(Branch.isp_name, func.count(Branch.id)).group_by(Branch.isp_name)
    ).all()
    isps_count = {str(i or "NOOR"): int(c) for i, c in isp_rows}

    return BranchListResponse(
        items=[BranchResponse.model_validate(b) for b in rows],
        total=int(total),
        limit=limit,
        offset=offset,
        regions_count=regions_count,
        isps_count=isps_count,
    )


def get_branch_by_id(db: Session, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise EntityNotFoundError("Branch", branch_id)
    return branch


def get_branch_by_code(db: Session, branch_code: str) -> Optional[Branch]:
    code = branch_code.strip()
    return db.execute(
        select(Branch).where(Branch.branch_code == code).limit(1)
    ).scalar_one_or_none()


def find_branch_by_hint(db: Session, text_or_code: str) -> Optional[Branch]:
    """Find a branch by SAP code, name, or circuit ID mentioned in an email/subject."""
    cleaned = text_or_code.strip()
    if not cleaned:
        return None
    direct = get_branch_by_code(db, cleaned)
    if direct is not None:
        return direct

    # Look for numeric or alphanumeric branch codes mentioned as tokens in the text
    tokens = re.findall(r"\b([A-Za-z0-9_-]{3,16})\b", cleaned)
    for tok in tokens:
        b = get_branch_by_code(db, tok)
        if b is not None:
            return b

    # Fallback: match by LL circuit ID, backup circuit ID, or store name
    q = f"%{cleaned.lower()}%"
    return db.execute(
        select(Branch)
        .where(
            or_(
                func.lower(Branch.name).like(q),
                func.lower(func.coalesce(Branch.ll_circuit_id, "")).like(q),
                func.lower(func.coalesce(Branch.backup_circuit_id, "")).like(q),
            )
        )
        .limit(1)
    ).scalar_one_or_none()


def query_branches_for_export(
    db: Session,
    *,
    search: Optional[str] = None,
    region: Optional[str] = None,
    isp_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> list[Branch]:
    """Return all branches matching filters ordered by `branch_code` for CSV/Excel export."""
    stmt = select(Branch)
    if search:
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Branch.branch_code).like(q),
                func.lower(Branch.name).like(q),
                func.lower(Branch.ip_1).like(q),
                func.lower(Branch.ip_2).like(q),
                func.lower(func.coalesce(Branch.ll_circuit_id, "")).like(q),
                func.lower(func.coalesce(Branch.backup_circuit_id, "")).like(q),
            )
        )
    if region and region.lower() != "all":
        stmt = stmt.where(func.lower(Branch.region) == region.strip().lower())
    if isp_name and isp_name.upper() != "ALL":
        stmt = stmt.where(func.upper(Branch.isp_name) == isp_name.strip().upper())
    if is_active is not None:
        stmt = stmt.where(Branch.is_active.is_(is_active))
    return list(db.execute(stmt.order_by(Branch.branch_code.asc())).scalars().all())


def create_branch(
    db: Session,
    payload: BranchCreateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> Branch:
    """Create a new branch record with automatic IP1/IP2 derivation if not overridden."""
    isps_map = ensure_default_isps(db)
    code = payload.branch_code.strip()
    existing = get_branch_by_code(db, code)
    if existing is not None:
        raise DuplicateResourceError(f"Branch with SAP code '{code}' already exists")

    derived_ip1, derived_ip2 = derive_branch_ips(code)
    ip_1 = (payload.ip_1 or "").strip() or derived_ip1
    ip_2 = (payload.ip_2 or "").strip() or derived_ip2
    isp_name = payload.isp_name.strip().upper()
    if isp_name == "ORANG":
        isp_name = "ORANGE"
    if isp_name not in {"NOOR", "ORANGE", "WE"}:
        isp_name = "NOOR"

    provider = isps_map.get(isp_name)
    default_isp_mail = (
        provider.support_email
        if provider and provider.support_email
        else str(ISP_DEFAULTS[isp_name]["support_email"])
    )
    isp_contact_mail = (payload.isp_contact_mail or "").strip() or default_isp_mail
    region = payload.region.strip() or "Cairo"
    regional_it_email = (payload.regional_it_email or "").strip() or REGIONAL_IT_DEFAULTS.get(
        region, "CITSupport@kazyon.com"
    )
    four_g_hub_ip = (payload.four_g_hub_ip or "").strip() or (
        "10.247.8.1" if isp_name == "ORANGE" else ("172.16.70.33" if isp_name == "WE" else None)
    )
    name = payload.name.strip()
    if not name.startswith(code):
        name = f"{code}-{name}"

    branch = Branch(
        branch_code=code,
        name=name,
        region=region,
        ip_1=ip_1,
        ip_2=ip_2,
        target_ip=ip_1,
        circuit_id=(payload.ll_circuit_id or "").strip() or f"{isp_name}-{code}",
        connection_type="MPLS_4G" if isp_name in {"ORANGE", "WE"} else "MPLS",
        isp_name=isp_name,
        isp_contact_mail=isp_contact_mail,
        regional_it_email=regional_it_email,
        four_g_hub_ip=four_g_hub_ip,
        ll_circuit_id=(payload.ll_circuit_id or "").strip() or None,
        backup_circuit_id=(payload.backup_circuit_id or "").strip() or None,
        contact_emails=[regional_it_email],
        isp_id=provider.id if provider else None,
        is_active=payload.is_active,
    )
    db.add(branch)
    db.flush()

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="branch.created",
        resource_type="branch",
        resource_id=branch.branch_code,
        summary=f"Created branch '{branch.name}' ({branch.isp_name})",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(branch)
    return branch


def update_branch(
    db: Session,
    branch_id: int,
    payload: BranchUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> Branch:
    """Update an existing branch record."""
    branch = get_branch_by_id(db, branch_id)
    isps_map = ensure_default_isps(db)

    if payload.branch_code is not None and payload.branch_code.strip() != branch.branch_code:
        new_code = payload.branch_code.strip()
        dup = get_branch_by_code(db, new_code)
        if dup is not None and dup.id != branch.id:
            raise DuplicateResourceError(f"Branch code '{new_code}' is already in use")
        branch.branch_code = new_code

    if payload.name is not None:
        branch.name = payload.name.strip()
    if payload.region is not None:
        branch.region = payload.region.strip()
    if payload.ip_1 is not None:
        branch.ip_1 = payload.ip_1.strip()
        branch.target_ip = branch.ip_1
    if payload.ip_2 is not None:
        branch.ip_2 = payload.ip_2.strip()
    if payload.regional_it_email is not None:
        branch.regional_it_email = payload.regional_it_email.strip() or None
    if payload.isp_name is not None:
        norm_isp = payload.isp_name.strip().upper()
        if norm_isp == "ORANG":
            norm_isp = "ORANGE"
        branch.isp_name = norm_isp
        prov = isps_map.get(norm_isp)
        if prov is not None:
            branch.isp_id = prov.id
    if payload.isp_contact_mail is not None:
        branch.isp_contact_mail = payload.isp_contact_mail.strip()
    if payload.four_g_hub_ip is not None:
        branch.four_g_hub_ip = payload.four_g_hub_ip.strip() or None
    if payload.ll_circuit_id is not None:
        branch.ll_circuit_id = payload.ll_circuit_id.strip() or None
        if branch.ll_circuit_id:
            branch.circuit_id = branch.ll_circuit_id
    if payload.backup_circuit_id is not None:
        branch.backup_circuit_id = payload.backup_circuit_id.strip() or None
    if payload.is_active is not None:
        branch.is_active = payload.is_active

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="branch.updated",
        resource_type="branch",
        resource_id=branch.branch_code,
        summary=f"Updated branch '{branch.name}' ({branch.branch_code})",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(branch)
    return branch


def delete_branch(
    db: Session,
    branch_id: int,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> None:
    """Delete a branch record and log an audit event."""
    branch = get_branch_by_id(db, branch_id)
    code = branch.branch_code
    name = branch.name
    db.delete(branch)
    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="branch.deleted",
        resource_type="branch",
        resource_id=code,
        summary=f"Deleted branch '{name}' ({code})",
        ip_address=ip_address,
    )
    db.commit()


def list_isps(db: Session) -> list[IspResponse]:
    """List the 3 Network Service Providers (`NOOR`, `ORANGE`, `WE`) with store counts."""
    ensure_default_isps(db)
    providers = (
        db.execute(select(NetworkProvider).order_by(NetworkProvider.id.asc())).scalars().all()
    )
    counts = dict(
        db.execute(select(Branch.isp_name, func.count(Branch.id)).group_by(Branch.isp_name)).all()
    )
    results: list[IspResponse] = []
    for p in providers:
        dto = IspResponse.model_validate(p)
        dto.store_count = int(counts.get(p.name.upper(), 0))
        results.append(dto)
    return results


def update_isp(
    db: Session,
    isp_id_or_name: str,
    payload: IspUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> IspResponse:
    """Update an ISP's support email, CC list, 4G hub IP, SLA timers, or escalation template."""
    ensure_default_isps(db)
    if isp_id_or_name.isdigit():
        provider = db.get(NetworkProvider, int(isp_id_or_name))
    else:
        provider = db.execute(
            select(NetworkProvider)
            .where(func.upper(NetworkProvider.name) == isp_id_or_name.strip().upper())
            .limit(1)
        ).scalar_one_or_none()
    if provider is None:
        raise EntityNotFoundError("NetworkProvider", isp_id_or_name)

    if payload.support_email is not None:
        new_support_email = payload.support_email.strip()
        provider.support_email = new_support_email
        if new_support_email:
            db.execute(
                update(Branch)
                .where(func.upper(Branch.isp_name) == provider.name.upper())
                .values(isp_contact_mail=new_support_email)
            )
    if payload.cc_emails is not None:
        provider.cc_emails = [e.strip() for e in payload.cc_emails if e.strip()]
    if payload.four_g_hub_ip is not None:
        provider.four_g_hub_ip = payload.four_g_hub_ip.strip() or None
    if payload.welcome_sla_minutes is not None:
        provider.welcome_sla_minutes = payload.welcome_sla_minutes
    if payload.followup_sla_minutes is not None:
        provider.followup_sla_minutes = payload.followup_sla_minutes
        provider.followup_interval_minutes = payload.followup_sla_minutes
    if payload.account_manager_email is not None:
        provider.account_manager_email = payload.account_manager_email.strip() or None
    if payload.escalation_template is not None:
        provider.escalation_template = payload.escalation_template
    if payload.is_active is not None:
        provider.is_active = payload.is_active

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="isp.updated",
        resource_type="isp",
        resource_id=provider.name,
        summary=f"Updated ISP configuration for '{provider.name}'",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(provider)

    store_count = db.execute(
        select(func.count())
        .select_from(Branch)
        .where(func.upper(Branch.isp_name) == provider.name.upper())
    ).scalar_one()
    dto = IspResponse.model_validate(provider)
    dto.store_count = int(store_count)
    return dto
