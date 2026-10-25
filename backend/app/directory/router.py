"""FastAPI routers for `/api/v1/branches` and `/api/v1/isps`."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.models import User
from app.common.audit import record_audit_event
from app.common.database import get_db
from app.directory.schemas import (
    BranchCreateRequest,
    BranchListResponse,
    BranchResponse,
    BranchUpdateRequest,
    IspResponse,
    IspUpdateRequest,
    SeedResultSummary,
)
from app.directory.seeder import (
    derive_branch_ips,
    generate_branches_csv_bytes,
    generate_branches_excel_bytes,
    seed_branches_from_excel,
)
from app.directory.service import (
    create_branch,
    delete_branch,
    get_branch_by_code,
    get_branch_by_id,
    list_branches,
    list_isps,
    query_branches_for_export,
    update_branch,
    update_isp,
)

branches_router = APIRouter(prefix="/api/v1/branches", tags=["Branches Directory"])
isps_router = APIRouter(prefix="/api/v1/isps", tags=["ISPs Directory"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@branches_router.get("", response_model=BranchListResponse)
async def get_branches_endpoint(
    search: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    isp_name: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("branches:view")),
) -> BranchListResponse:
    """List and filter Kazyon store branches."""
    return list_branches(
        db,
        search=search,
        region=region,
        isp_name=isp_name,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@branches_router.get("/template")
async def download_branch_template_endpoint(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    _user: User = Depends(require_permission("branches:view")),
) -> Response:
    """Download a sample CSV or Excel (`.xlsx`) branch import template (Columns A–K)."""
    if format.lower() == "xlsx":
        data = await asyncio.to_thread(generate_branches_excel_bytes, None)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="kazyon-branches-template.xlsx"'},
        )
    data = await asyncio.to_thread(generate_branches_csv_bytes, None)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kazyon-branches-template.csv"'},
    )


@branches_router.get("/export")
async def export_branches_endpoint(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    search: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    isp_name: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("branches:view")),
) -> Response:
    """Export matching branches to CSV or Excel (`.xlsx`)."""
    rows = query_branches_for_export(
        db,
        search=search,
        region=region,
        isp_name=isp_name,
        is_active=is_active,
    )
    if format.lower() == "xlsx":
        data = await asyncio.to_thread(generate_branches_excel_bytes, rows)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="kazyon-branches-export.xlsx"'},
        )
    data = await asyncio.to_thread(generate_branches_csv_bytes, rows)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kazyon-branches-export.csv"'},
    )


@branches_router.get("/derive-ips/{branch_code}")
async def derive_ips_endpoint(
    branch_code: str,
    _user: User = Depends(require_permission("branches:view")),
) -> dict[str, str]:
    """Derive IP1 (`10.<AB>.<CD>.1`) and IP2 (`10.<AB>.<CD>.2`) from a 4-digit SAP code."""
    ip1, ip2 = derive_branch_ips(branch_code)
    return {"branch_code": branch_code, "ip_1": ip1, "ip_2": ip2}


@branches_router.get("/by-code/{branch_code}", response_model=BranchResponse)
async def get_branch_by_code_endpoint(
    branch_code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("branches:view")),
) -> BranchResponse:
    """Lookup a single branch by its SAP code."""
    branch = get_branch_by_code(db, branch_code)
    if branch is None:
        from app.common.exceptions import EntityNotFoundError

        raise EntityNotFoundError("Branch", branch_code)
    return BranchResponse.model_validate(branch)


@branches_router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch_endpoint(
    branch_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("branches:view")),
) -> BranchResponse:
    """Lookup a single branch by primary key."""
    return BranchResponse.model_validate(get_branch_by_id(db, branch_id))


@branches_router.post("", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch_endpoint(
    payload: BranchCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("branches:create")),
) -> BranchResponse:
    """Create a new store branch."""
    branch = create_branch(db, payload, actor=actor, ip_address=_client_ip(request))
    return BranchResponse.model_validate(branch)


@branches_router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch_endpoint(
    branch_id: int,
    payload: BranchUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("branches:edit")),
) -> BranchResponse:
    """Update an existing store branch."""
    branch = update_branch(db, branch_id, payload, actor=actor, ip_address=_client_ip(request))
    return BranchResponse.model_validate(branch)


@branches_router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch_endpoint(
    branch_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("branches:edit")),
) -> None:
    """Delete a store branch."""
    delete_branch(db, branch_id, actor=actor, ip_address=_client_ip(request))


@branches_router.post("/seed-excel", response_model=SeedResultSummary)
async def seed_branches_excel_endpoint(
    request: Request,
    dry_run: bool = Query(default=False),
    replace_existing: bool = Query(default=False),
    file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("branches:import_sheet")),
) -> SeedResultSummary:
    """Bulk seed or preview (`dry_run=true`) branches from an uploaded CSV/Excel file or default Excel directory."""
    raw_bytes: Optional[bytes] = None
    filename = "Copy of All store ISP (2).xlsx"
    if file is not None:
        raw_bytes = await file.read()
        filename = file.filename or filename

    summary = await asyncio.to_thread(
        seed_branches_from_excel,
        db,
        excel_source=raw_bytes,
        source_filename=filename,
        dry_run=dry_run,
        replace_existing=replace_existing,
    )
    if not dry_run:
        record_audit_event(
            db,
            actor_user_id=actor.id,
            actor_username=actor.username,
            action="branch.seed_excel",
            resource_type="branch",
            summary=(
                f"Applied bulk sheet '{filename}': "
                f"{summary.total_rows_parsed} rows ({summary.created_count} new, "
                f"{summary.updated_count} updated, {summary.unchanged_count} unchanged, "
                f"{summary.deleted_count} deleted)"
            ),
            ip_address=_client_ip(request),
            commit=True,
        )
    return summary


@isps_router.get("", response_model=list[IspResponse])
async def list_isps_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("branches:view")),
) -> list[IspResponse]:
    """List the 3 Network Service Providers (`NOOR`, `ORANGE`, `WE`) and their configurations."""
    return list_isps(db)


@isps_router.put("/{isp_id_or_name}", response_model=IspResponse)
async def update_isp_endpoint(
    isp_id_or_name: str,
    payload: IspUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("isps:manage")),
) -> IspResponse:
    """Update an ISP's support email, CC list, 4G hub IP, SLA timers, or escalation template."""
    return update_isp(db, isp_id_or_name, payload, actor=actor, ip_address=_client_ip(request))
