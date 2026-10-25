"""Excel (`.xlsx`) and CSV (`.csv`) parser, exporter, and idempotent upsert seeder for branches and ISPs."""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

import openpyxl
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.directory.models import Branch, NetworkProvider
from app.directory.schemas import SeedResultSummary, SeedRowPreview

logger = logging.getLogger("it_net.directory.seeder")

DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "Info" / "Copy of All store ISP (2).xlsx"
)

REGIONAL_IT_DEFAULTS: dict[str, str] = {
    "Behera": "BITSupport@kazyon.com",
    "Cairo": "CITSupport@kazyon.com",
    "New October": "newoctregion@kazyon.com",
    "Assyut": "assiutregion@kazyon.com",
    "Giza": "GITSupport@kazyon.com",
}

ISP_DEFAULTS: dict[str, dict[str, Any]] = {
    "NOOR": {
        "name": "NOOR",
        "support_email": "noc@noor.net",
        "cc_emails": ["ITInfrastructure@kazyon.com"],
        "four_g_hub_ip": None,
        "welcome_sla_minutes": 120,
        "followup_sla_minutes": 300,
        "escalation_template": (
            "Subject: store <SAP_CODE>\n\n"
            "Dear NOC\n"
            "Kindly check connection store <SAP_CODE>\n"
            "site contact : <PHONE>"
        ),
    },
    "ORANGE": {
        "name": "ORANGE",
        "support_email": "ccc-eg@orange.com",
        "cc_emails": ["ITInfrastructure@kazyon.com"],
        "four_g_hub_ip": "10.247.8.1",
        "welcome_sla_minutes": 120,
        "followup_sla_minutes": 300,
        "escalation_template": (
            "Subject: store <SAP_CODE> # <LL_ID>\n\n"
            "Dear NOC\n"
            "kindly check L.L and 4G connection store <SAP_CODE>\n"
            "<SAP_CODE>\n"
            "<LL_ID>\n"
            "<3G_ID>\n"
            "site contact : <PHONE>"
        ),
    },
    "WE": {
        "name": "WE",
        "support_email": "psupport@te.eg",
        "cc_emails": ["ITInfrastructure@kazyon.com"],
        "four_g_hub_ip": "172.16.70.33, 172.17.20.33",
        "welcome_sla_minutes": 120,
        "followup_sla_minutes": 300,
        "escalation_template": (
            "Subject: Kazyon #E33209 #<LL_ID> #<3G_ID> #<SAP_CODE>\n\n"
            "Dear support\n"
            "kindly check LL & 4G connection\n"
            "LL order number : <LL_ID>\n"
            "4G order number : <3G_ID>\n"
            "site contact <PHONE>\n"
            "site work from 9 AM to 12 AM\n"
            "power working fine at site"
        ),
    },
}

SHEET_HEADERS: list[str] = [
    "SAP Code",
    "Store Name",
    "IP Router",
    "server",
    "Region",
    "E-Mail",
    "Regional IT Mail",
    "ISP",
    "3G",
    "L.L ID",
    "3G ID",
]

SAMPLE_TEMPLATE_ROWS: list[list[str]] = [
    [
        "2009",
        "2009-Kafr Nasar",
        "10.20.9.1",
        "10.20.9.2",
        "Giza",
        "NOC <noc@noor.net>",
        "GITSupport@kazyon.com",
        "NOOR",
        "",
        "",
        "",
    ],
    [
        "1173",
        "1173-Ghmrawy",
        "10.11.73.1",
        "10.11.73.2",
        "Cairo",
        "Egypt ccc <ccc-eg@orange.com>",
        "CITSupport@kazyon.com",
        "ORANGE",
        "10.247.8.1",
        "QUO1-10316406",
        "QUO1-10316407",
    ],
    [
        "1088",
        "1088-Gamal Salem",
        "10.10.88.1",
        "10.10.88.2",
        "New October",
        "psupport <psupport@te.eg>",
        "newoctregion@kazyon.com",
        "WE",
        "172.16.70.33",
        "6175613",
        "6181290",
    ],
]

HEADER_ALIASES: dict[str, set[str]] = {
    "branch_code": {
        "sap code",
        "sap",
        "sap_code",
        "branch_code",
        "branch code",
        "store code",
        "store_code",
        "store id",
        "store_id",
        "code",
        "id",
    },
    "name": {
        "store name",
        "store_name",
        "branch name",
        "branch_name",
        "name",
        "store",
        "branch",
    },
    "ip_1": {
        "ip router",
        "ip_router",
        "router ip",
        "ip 1",
        "ip1",
        "ip_1",
        "gateway",
        "router",
    },
    "ip_2": {
        "server",
        "ip server",
        "ip switch",
        "switch ip",
        "server switch",
        "ip 2",
        "ip2",
        "ip_2",
        "switch",
    },
    "region": {
        "region",
        "area",
        "zone",
        "governorate",
        "city",
    },
    "isp_contact_mail": {
        "e-mail",
        "email",
        "isp email",
        "isp_email",
        "isp mail",
        "isp_contact_mail",
        "support email",
    },
    "regional_it_email": {
        "regional it",
        "regional it mail",
        "regional it email",
        "regional_it_email",
        "regional_it",
        "it mail",
        "it email",
        "col g",
    },
    "isp_name": {
        "isp",
        "isp_name",
        "isp name",
        "provider",
        "network provider",
    },
    "four_g_hub_ip": {
        "3g",
        "4g",
        "3g hub",
        "4g hub",
        "3g/4g hub",
        "3g / 4g hub ip",
        "four_g_hub_ip",
        "hub ip",
        "hub",
    },
    "ll_circuit_id": {
        "l.l id",
        "ll id",
        "l.l",
        "ll_id",
        "ll_circuit_id",
        "local loop id",
        "circuit id",
        "circuit_id",
    },
    "backup_circuit_id": {
        "3g id",
        "4g id",
        "3g_id",
        "4g_id",
        "backup_circuit_id",
        "backup id",
        "3g order",
    },
}


def derive_branch_ips(branch_code: str) -> tuple[str, str]:
    """Derive IP1 (`10.<AB>.<CD>.1`) and IP2 (`10.<AB>.<CD>.2`) from a 4-digit SAP code."""
    digits = re.sub(r"\D", "", str(branch_code))
    if len(digits) >= 4:
        ab = int(digits[:2])
        cd = int(digits[2:4])
        return f"10.{ab}.{cd}.1", f"10.{ab}.{cd}.2"
    if len(digits) > 0:
        num = int(digits)
        ab = (num // 100) % 255
        cd = num % 100
        return f"10.{ab}.{cd}.1", f"10.{ab}.{cd}.2"
    return "10.0.0.1", "10.0.0.2"


def normalize_isp_name(raw_isp: Optional[str], raw_email: Optional[str] = None) -> tuple[str, bool]:
    """Normalize ISP string (`NOOR`, `Orang`/`ORANGE`, `WE`) and flag if 'Orang' was normalized."""
    val = (raw_isp or "").strip()
    was_warning = False
    if val.lower() == "orang":
        was_warning = True
        return "ORANGE", was_warning
    upper = val.upper()
    if upper in {"NOOR", "ORANGE", "WE"}:
        return upper, False
    if "ORANGE" in upper:
        return "ORANGE", True
    if upper in {"TE", "TELECOM EGYPT", "WE / TELECOM EGYPT"}:
        return "WE", True
    if "NOOR" in upper:
        return "NOOR", True
    email_lower = (raw_email or "").lower()
    if "orange" in email_lower:
        return "ORANGE", True
    if "te.eg" in email_lower or "psupport" in email_lower:
        return "WE", True
    return "NOOR", False


def extract_clean_email(raw_email: Optional[str], isp_name: str) -> str:
    """Extract clean email from strings like `NOC <noc@noor.net>` or fallback to ISP default."""
    if raw_email:
        match = re.search(r"<([^>]+@[^>]+)>", str(raw_email))
        if match:
            return match.group(1).strip()
        plain = str(raw_email).strip()
        if "@" in plain:
            return plain
    return str(ISP_DEFAULTS.get(isp_name, ISP_DEFAULTS["NOOR"])["support_email"])


def ensure_default_isps(db: Session) -> dict[str, NetworkProvider]:
    """Ensure the 3 canonical ISPs (`NOOR`, `ORANGE`, `WE`) exist in `network_providers`."""
    existing = {p.name.upper(): p for p in db.execute(select(NetworkProvider)).scalars().all()}
    changed = False
    for isp_key, cfg in ISP_DEFAULTS.items():
        if isp_key not in existing:
            provider = NetworkProvider(
                name=cfg["name"],
                support_email=cfg["support_email"],
                cc_emails=list(cfg["cc_emails"]),
                four_g_hub_ip=cfg["four_g_hub_ip"],
                welcome_sla_minutes=cfg["welcome_sla_minutes"],
                followup_sla_minutes=cfg["followup_sla_minutes"],
                followup_interval_minutes=cfg["followup_sla_minutes"],
                escalation_template=cfg["escalation_template"],
                is_active=True,
            )
            db.add(provider)
            existing[isp_key] = provider
            changed = True
        else:
            prov = existing[isp_key]
            if not prov.escalation_template:
                prov.escalation_template = cfg["escalation_template"]
                changed = True
            if prov.four_g_hub_ip is None and cfg["four_g_hub_ip"] is not None:
                prov.four_g_hub_ip = cfg["four_g_hub_ip"]
                changed = True
    if changed:
        db.commit()
        for prov in existing.values():
            db.refresh(prov)
    return existing


def _clean_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def _build_column_map(header_row: list[Any]) -> Optional[dict[str, int]]:
    """Detect whether `header_row` contains column headers and map field names to column indices."""
    cleaned_headers = [_clean_cell(c).lower() for c in header_row]
    matched: dict[str, int] = {}
    for col_idx, h in enumerate(cleaned_headers):
        if not h:
            continue
        for field_name, aliases in HEADER_ALIASES.items():
            if field_name not in matched and h in aliases:
                matched[field_name] = col_idx
                break

    if "branch_code" not in matched and "name" not in matched:
        return None

    # Standard Kazyon Excel sheet (`Copy of All store ISP (2).xlsx`) has an unnamed Col G (index 6)
    # for Regional IT email when Col F (5) is E-Mail and Col H (7) is ISP.
    if (
        "regional_it_email" not in matched
        and matched.get("isp_contact_mail") == 5
        and matched.get("isp_name") == 7
        and len(header_row) > 6
        and not cleaned_headers[6]
    ):
        matched["regional_it_email"] = 6

    # Fill standard positional defaults if not explicitly matched by header name
    positional_defaults = [
        ("branch_code", 0),
        ("name", 1),
        ("ip_1", 2),
        ("ip_2", 3),
        ("region", 4),
        ("isp_contact_mail", 5),
        ("regional_it_email", 6),
        ("isp_name", 7),
        ("four_g_hub_ip", 8),
        ("ll_circuit_id", 9),
        ("backup_circuit_id", 10),
    ]
    used_indices = set(matched.values())
    for field_name, pos_idx in positional_defaults:
        if field_name not in matched and pos_idx not in used_indices and pos_idx < len(header_row):
            if not cleaned_headers[pos_idx]:
                matched[field_name] = pos_idx
                used_indices.add(pos_idx)

    return matched


def _parse_csv_rows(raw_bytes: bytes) -> list[list[Any]]:
    """Decode CSV bytes (UTF-8 / UTF-8-SIG / CP1252 / Latin-1) and parse rows with auto-detected delimiter."""
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text.strip():
        return []

    sample = text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        if sample.count(";") > sample.count(","):
            delimiter = ";"
        elif sample.count("\t") > sample.count(","):
            delimiter = "\t"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(r) for r in reader if any(str(c).strip() for c in r)]


def _extract_raw_rows(
    excel_source: Optional[Union[Path, bytes]],
    source_filename: str,
) -> tuple[list[list[Any]], list[str]]:
    """Load rows from either a `.csv` or `.xlsx` source (file path or uploaded bytes)."""
    fname_lower = (source_filename or "").lower()

    if excel_source is None:
        path = DEFAULT_EXCEL_PATH
        if not path.exists():
            logger.warning("Excel seed file not found at %s", path)
            return [], [f"Excel file not found: {path}"]
        wb = openpyxl.load_workbook(filename=str(path), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            wb.close()
            return [], ["Workbook has no active worksheet"]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, []

    if isinstance(excel_source, Path):
        if not excel_source.exists():
            return [], [f"File not found: {excel_source}"]
        if excel_source.suffix.lower() == ".csv":
            return _parse_csv_rows(excel_source.read_bytes()), []
        wb = openpyxl.load_workbook(filename=str(excel_source), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            wb.close()
            return [], ["Workbook has no active worksheet"]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, []

    # `excel_source` is `bytes`
    is_zip_xlsx = excel_source[:4] == b"PK\x03\x04"
    if fname_lower.endswith(".csv") or not is_zip_xlsx:
        try:
            csv_rows = _parse_csv_rows(excel_source)
            if csv_rows:
                return csv_rows, []
        except Exception as exc:
            if fname_lower.endswith(".csv"):
                return [], [f"Could not parse CSV file '{source_filename}': {exc}"]

    try:
        wb = openpyxl.load_workbook(
            filename=io.BytesIO(excel_source), read_only=True, data_only=True
        )
        ws = wb.active
        if ws is None:
            wb.close()
            return [], ["Workbook has no active worksheet"]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, []
    except Exception as exc:
        return [], [f"Could not parse file '{source_filename}' as Excel or CSV: {exc}"]


def seed_branches_from_excel(
    db: Session,
    *,
    excel_source: Optional[Union[Path, bytes]] = None,
    source_filename: str = "Copy of All store ISP (2).xlsx",
    dry_run: bool = False,
    replace_existing: bool = False,
) -> SeedResultSummary:
    """Parse an Excel (`.xlsx`) or CSV (`.csv`) sheet and idempotently upsert (or replace) branches."""
    isps_map = ensure_default_isps(db)
    raw_rows, parse_errors = _extract_raw_rows(excel_source, source_filename)
    if parse_errors or not raw_rows:
        return SeedResultSummary(
            dry_run=dry_run,
            replace_existing=replace_existing,
            source_filename=source_filename,
            total_rows_parsed=0,
            unchanged_count=0,
            updated_count=0,
            created_count=0,
            deleted_count=0,
            warnings_count=len(parse_errors) or 1,
            warnings=parse_errors or ["Uploaded file contains no data rows."],
        )

    col_map = _build_column_map(raw_rows[0])
    start_row_idx = 1 if col_map is not None else 0
    if col_map is None:
        col_map = {
            "branch_code": 0,
            "name": 1,
            "ip_1": 2,
            "ip_2": 3,
            "region": 4,
            "isp_contact_mail": 5,
            "regional_it_email": 6,
            "isp_name": 7,
            "four_g_hub_ip": 8,
            "ll_circuit_id": 9,
            "backup_circuit_id": 10,
        }

    def _cell(row_vals: list[Any], field: str) -> str:
        idx = col_map.get(field)
        if idx is None or idx >= len(row_vals):
            return ""
        return _clean_cell(row_vals[idx])

    existing_branches: dict[str, Branch] = {
        b.branch_code: b for b in db.execute(select(Branch)).scalars().all()
    }

    total_rows = 0
    unchanged = 0
    updated = 0
    created = 0
    warnings_list: list[str] = []
    orang_normalized_count = 0
    by_isp: dict[str, int] = {"NOOR": 0, "ORANGE": 0, "WE": 0}
    by_region: dict[str, int] = {}
    preview_rows: list[SeedRowPreview] = []
    seen_codes_in_sheet: set[str] = set()

    for row in raw_rows[start_row_idx:]:
        if not row:
            continue
        branch_code = _cell(row, "branch_code")
        raw_name_cell = _cell(row, "name")
        if not branch_code and not raw_name_cell:
            continue
        if not branch_code and raw_name_cell:
            # Try to extract leading code from store name like "2009-Kafr Nasar"
            m = re.match(r"^([A-Za-z0-9]+)\s*[-_]\s*(.+)$", raw_name_cell)
            if m:
                branch_code = m.group(1).strip()
            else:
                branch_code = re.sub(r"\W+", "", raw_name_cell)[:16] or "0000"

        if branch_code in seen_codes_in_sheet:
            warnings_list.append(
                f"Duplicate SAP code '{branch_code}' in uploaded sheet (latest row applied)"
            )
        seen_codes_in_sheet.add(branch_code)

        total_rows += 1
        raw_name = raw_name_cell or f"{branch_code}-Store"
        if not raw_name.startswith(branch_code):
            raw_name = f"{branch_code}-{raw_name}"

        derived_ip1, derived_ip2 = derive_branch_ips(branch_code)
        raw_ip1 = _cell(row, "ip_1") or derived_ip1
        raw_ip2 = _cell(row, "ip_2") or derived_ip2
        parts1 = raw_ip1.split(".")
        ip_1 = (
            ".".join(str(int(p)) for p in parts1)
            if len(parts1) == 4 and all(p.isdigit() for p in parts1)
            else raw_ip1
        )
        parts2 = raw_ip2.split(".")
        ip_2 = (
            ".".join(str(int(p)) for p in parts2)
            if len(parts2) == 4 and all(p.isdigit() for p in parts2)
            else raw_ip2
        )
        region = _cell(row, "region") or "Cairo"
        raw_isp_mail = _cell(row, "isp_contact_mail") or None
        raw_reg_it = _cell(row, "regional_it_email") or None
        raw_isp_name = _cell(row, "isp_name") or None
        raw_hub_ip = _cell(row, "four_g_hub_ip") or None
        raw_ll_id = _cell(row, "ll_circuit_id") or None
        raw_3g_id = _cell(row, "backup_circuit_id") or None

        isp_name, was_norm = normalize_isp_name(raw_isp_name, raw_isp_mail)
        if was_norm:
            orang_normalized_count += 1

        isp_contact_mail = extract_clean_email(raw_isp_mail, isp_name)
        regional_it_email = raw_reg_it or REGIONAL_IT_DEFAULTS.get(region, "CITSupport@kazyon.com")
        four_g_hub_ip = raw_hub_ip
        if not four_g_hub_ip and isp_name == "ORANGE":
            four_g_hub_ip = "10.247.8.1"
        elif not four_g_hub_ip and isp_name == "WE":
            four_g_hub_ip = "172.16.70.33"

        provider = isps_map.get(isp_name)
        isp_id = provider.id if provider else None

        by_isp[isp_name] = by_isp.get(isp_name, 0) + 1
        by_region[region] = by_region.get(region, 0) + 1

        existing_branch = existing_branches.get(branch_code)
        row_action = "UNCHANGED"
        if existing_branch is None:
            created += 1
            row_action = "CREATED"
            if not dry_run:
                new_branch = Branch(
                    branch_code=branch_code,
                    name=raw_name,
                    region=region,
                    ip_1=ip_1,
                    ip_2=ip_2,
                    target_ip=ip_1,
                    circuit_id=raw_ll_id or f"{isp_name}-{branch_code}",
                    connection_type="MPLS_4G" if isp_name in {"ORANGE", "WE"} else "MPLS",
                    isp_name=isp_name,
                    isp_contact_mail=isp_contact_mail,
                    regional_it_email=regional_it_email,
                    four_g_hub_ip=four_g_hub_ip,
                    ll_circuit_id=raw_ll_id,
                    backup_circuit_id=raw_3g_id,
                    contact_emails=[regional_it_email] if regional_it_email else [],
                    isp_id=isp_id,
                    is_active=True,
                )
                db.add(new_branch)
                existing_branches[branch_code] = new_branch
        else:
            diffs = (
                existing_branch.name != raw_name
                or existing_branch.region != region
                or existing_branch.ip_1 != ip_1
                or existing_branch.ip_2 != ip_2
                or existing_branch.isp_name != isp_name
                or existing_branch.isp_contact_mail != isp_contact_mail
                or existing_branch.regional_it_email != regional_it_email
                or existing_branch.four_g_hub_ip != four_g_hub_ip
                or existing_branch.ll_circuit_id != raw_ll_id
                or existing_branch.backup_circuit_id != raw_3g_id
            )
            if diffs:
                updated += 1
                row_action = "UPDATED"
                if not dry_run:
                    existing_branch.name = raw_name
                    existing_branch.region = region
                    existing_branch.ip_1 = ip_1
                    existing_branch.ip_2 = ip_2
                    existing_branch.target_ip = ip_1
                    existing_branch.circuit_id = raw_ll_id or f"{isp_name}-{branch_code}"
                    existing_branch.isp_name = isp_name
                    existing_branch.isp_contact_mail = isp_contact_mail
                    existing_branch.regional_it_email = regional_it_email
                    existing_branch.four_g_hub_ip = four_g_hub_ip
                    existing_branch.ll_circuit_id = raw_ll_id
                    existing_branch.backup_circuit_id = raw_3g_id
                    existing_branch.isp_id = isp_id
            else:
                unchanged += 1
                row_action = "UNCHANGED"

        if len(preview_rows) < 100:
            preview_rows.append(
                SeedRowPreview(
                    action=row_action,
                    branch_code=branch_code,
                    name=raw_name,
                    region=region,
                    ip_1=ip_1,
                    ip_2=ip_2,
                    isp_name=isp_name,
                    isp_contact_mail=isp_contact_mail,
                    regional_it_email=regional_it_email,
                    four_g_hub_ip=four_g_hub_ip,
                    ll_circuit_id=raw_ll_id,
                    backup_circuit_id=raw_3g_id,
                )
            )

    deleted_count = 0
    if replace_existing and seen_codes_in_sheet:
        codes_to_delete = [c for c in existing_branches if c not in seen_codes_in_sheet]
        deleted_count = len(codes_to_delete)
        if not dry_run and codes_to_delete:
            db.execute(delete(Branch).where(Branch.branch_code.in_(codes_to_delete)))

    if orang_normalized_count > 0:
        warnings_list.append(
            f"Normalized '{orang_normalized_count}' rows with ISP='Orang' to 'ORANGE'"
        )

    if not dry_run:
        db.commit()
        logger.info(
            "Seeded %d branches from '%s' (created=%d, updated=%d, unchanged=%d, deleted=%d)",
            total_rows,
            source_filename,
            created,
            updated,
            unchanged,
            deleted_count,
        )

    return SeedResultSummary(
        dry_run=dry_run,
        replace_existing=replace_existing,
        source_filename=source_filename,
        total_rows_parsed=total_rows,
        unchanged_count=unchanged,
        updated_count=updated,
        created_count=created,
        deleted_count=deleted_count,
        warnings_count=len(warnings_list),
        warnings=warnings_list,
        by_isp=by_isp,
        by_region=by_region,
        preview_rows=preview_rows,
    )


def generate_branches_csv_bytes(branches: Optional[list[Branch]] = None) -> bytes:
    """Generate a UTF-8 CSV file (Columns A–K) for either a template (`branches=None`) or branch export."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(SHEET_HEADERS)
    if branches is None:
        for row in SAMPLE_TEMPLATE_ROWS:
            writer.writerow(row)
    else:
        for b in branches:
            writer.writerow(
                [
                    b.branch_code,
                    b.name,
                    b.ip_1,
                    b.ip_2,
                    b.region or "Cairo",
                    b.isp_contact_mail,
                    b.regional_it_email or "",
                    b.isp_name,
                    b.four_g_hub_ip or "",
                    b.ll_circuit_id or "",
                    b.backup_circuit_id or "",
                ]
            )
    return buf.getvalue().encode("utf-8-sig")


def generate_branches_excel_bytes(branches: Optional[list[Branch]] = None) -> bytes:
    """Generate an `.xlsx` workbook (Columns A–K) for either a template (`branches=None`) or branch export."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Branches Directory"
    ws.append(SHEET_HEADERS)
    if branches is None:
        for row in SAMPLE_TEMPLATE_ROWS:
            ws.append(row)
    else:
        for b in branches:
            ws.append(
                [
                    b.branch_code,
                    b.name,
                    b.ip_1,
                    b.ip_2,
                    b.region or "Cairo",
                    b.isp_contact_mail,
                    b.regional_it_email or "",
                    b.isp_name,
                    b.four_g_hub_ip or "",
                    b.ll_circuit_id or "",
                    b.backup_circuit_id or "",
                ]
            )
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()
