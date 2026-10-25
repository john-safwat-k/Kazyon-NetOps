"""MIME `.eml` parser, Replication Dashboard HTML table parser, and thread correlation helpers."""

from __future__ import annotations

import email
import email.policy
import email.utils
import hashlib
import re
import shutil
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.common.config import get_settings
from app.common.contracts import EmailEnvelope

MAX_IMAGE_ATTACHMENTS = 5
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class _SimpleHTMLTableParser(HTMLParser):
    """Lightweight HTML table parser for extracting `Replication Dashboard` store rows."""

    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t == "tr":
            self.in_tr = True
            self.current_row = []
        elif t in {"td", "th"} and self.in_tr:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"td", "th"} and self.in_cell:
            self.in_cell = False
            text = re.sub(r"\s+", " ", "".join(self.current_cell)).strip()
            self.current_row.append(text)
        elif t == "tr" and self.in_tr:
            self.in_tr = False
            if any(c for c in self.current_row):
                self.rows.append(self.current_row)


def strip_html_tags(html_text: str) -> str:
    """Convert HTML body into readable plain text."""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", html_text)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p>|</tr>|</div>", "\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in cleaned.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _guess_image_ext(filename: Optional[str], content_type: str) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower().strip()
        if ext in {"jpg", "jpeg", "png", "webp", "gif", "bmp"}:
            return ext
    ct = content_type.lower()
    if "png" in ct:
        return "png"
    if "webp" in ct:
        return "webp"
    if "gif" in ct:
        return "gif"
    return "jpg"


def _persist_image_attachment(
    payload_bytes: bytes,
    filename: Optional[str],
    content_type: str,
    ticket_folder: str = "_staging",
) -> Optional[tuple[str, str]]:
    """Persist an image attachment to `<attachments_dir>/<ticket_folder>/<sha256>.<ext>`."""
    if not payload_bytes or len(payload_bytes) > MAX_IMAGE_BYTES:
        return None
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    ext = _guess_image_ext(filename, content_type)
    base_dir = Path(get_settings().attachments_dir)
    target_dir = base_dir / ticket_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"{sha256}.{ext}"
    if not dest.exists():
        dest.write_bytes(payload_bytes)
    return str(dest), sha256


def relocate_attachments_to_ticket(
    attachments: list[dict[str, Any]],
    ticket_number: str,
) -> list[str]:
    """Move or copy staged attachment files into `data/attachments/<ticket_number>/<sha256>.<ext>`."""
    stored_paths: list[str] = []
    base_dir = Path(get_settings().attachments_dir)
    safe_ticket = re.sub(r"[^A-Za-z0-9_-]", "_", ticket_number or "_unassigned")
    target_dir = base_dir / safe_ticket
    target_dir.mkdir(parents=True, exist_ok=True)

    for att in attachments:
        src_str = att.get("stored_path")
        if src_str:
            src_path = Path(str(src_str))
            if src_path.exists():
                dest_path = target_dir / src_path.name
                if src_path.resolve() != dest_path.resolve():
                    shutil.copy2(src_path, dest_path)
                    if "_staging" in src_path.parts:
                        try:
                            src_path.unlink()
                        except OSError:
                            pass
                att["stored_path"] = str(dest_path)
                stored_paths.append(str(dest_path))
                continue
        if att.get("filename"):
            stored_paths.append(str(att["filename"]))
    return stored_paths


def read_attachment_image_bytes(attachments: list[dict[str, Any]]) -> list[bytes]:
    """Read persisted image bytes from `stored_path` entries on an `EmailEnvelope.attachments` list."""
    images: list[bytes] = []
    for att in attachments[:MAX_IMAGE_ATTACHMENTS]:
        sp = att.get("stored_path")
        if not sp:
            continue
        p = Path(str(sp))
        if p.exists() and p.is_file():
            data = p.read_bytes()
            if 0 < len(data) <= MAX_IMAGE_BYTES:
                images.append(data)
    return images


def parse_eml_bytes(raw_bytes: bytes) -> EmailEnvelope:
    """Parse raw RFC-5322 `.eml` bytes into an immutable `EmailEnvelope` and persist image bytes."""
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    raw_mid = str(msg.get("Message-ID") or "").strip()
    message_id = raw_mid if raw_mid else f"<{uuid4().hex}@kazyon-netops.local>"

    in_reply_to = str(msg.get("In-Reply-To") or "").strip() or None
    refs_header = str(msg.get("References") or "").strip()
    references = [r.strip() for r in refs_header.split() if r.strip()]

    sender_raw = str(msg.get("From") or "unknown@kazyon.com")
    _, sender_addr = email.utils.parseaddr(sender_raw)
    sender = sender_addr or sender_raw.strip()

    to_list = [addr for _, addr in email.utils.getaddresses(msg.get_all("To", [])) if addr]
    cc_list = [addr for _, addr in email.utils.getaddresses(msg.get_all("Cc", [])) if addr]
    subject = str(msg.get("Subject") or "(No Subject)").strip()

    date_hdr = msg.get("Date")
    received_at = datetime.now(timezone.utc)
    if date_hdr:
        try:
            dt = email.utils.parsedate_to_datetime(str(date_hdr))
            received_at = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            received_at = datetime.now(timezone.utc)

    body_text_parts: list[str] = []
    body_html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    image_count = 0

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get_content_disposition() or "")
            filename = part.get_filename()
            is_image = content_type.startswith("image/") or (
                filename is not None
                and filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
            )
            if filename or disp == "attachment" or is_image:
                payload_bytes = part.get_payload(decode=True)
                raw_part_bytes = payload_bytes if isinstance(payload_bytes, bytes) else b""
                size_bytes = len(raw_part_bytes)
                att_dict: dict[str, Any] = {
                    "filename": filename or f"attachment_{len(attachments) + 1}.jpg",
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                }
                if (
                    is_image
                    and image_count < MAX_IMAGE_ATTACHMENTS
                    and 0 < size_bytes <= MAX_IMAGE_BYTES
                ):
                    persisted = _persist_image_attachment(raw_part_bytes, filename, content_type)
                    if persisted is not None:
                        stored_path, sha256 = persisted
                        att_dict["stored_path"] = stored_path
                        att_dict["sha256"] = sha256
                        image_count += 1
                attachments.append(att_dict)
            elif content_type == "text/plain" and disp != "attachment":
                try:
                    txt = part.get_content()
                    if isinstance(txt, str):
                        body_text_parts.append(txt)
                except Exception:
                    pass
            elif content_type == "text/html" and disp != "attachment":
                try:
                    htm = part.get_content()
                    if isinstance(htm, str):
                        body_html_parts.append(htm)
                except Exception:
                    pass
    else:
        ctype = msg.get_content_type()
        try:
            content = msg.get_content()
            if isinstance(content, str):
                if ctype == "text/html":
                    body_html_parts.append(content)
                else:
                    body_text_parts.append(content)
        except Exception:
            pass

    body_html = "\n".join(body_html_parts).strip() or None
    body_text = "\n".join(body_text_parts).strip()
    if not body_text and body_html:
        body_text = strip_html_tags(body_html)

    raw_headers: dict[str, str] = {}
    for k, v in msg.items():
        raw_headers[str(k)] = str(v)

    return EmailEnvelope(
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        sender=sender,
        recipients=to_list,
        cc=cc_list,
        subject=subject,
        body_text=body_text or "(Empty body)",
        body_html=body_html,
        received_at=received_at,
        raw_headers=raw_headers,
        attachments=attachments,
    )


def parse_replication_dashboard_html(html_or_text: str) -> list[dict[str, str]]:
    """Extract store rows from a `Replication Dashboard - <Date>` HTML table.

    Columns: `ID`, `Store Name`, `Region`, `Last Trans.`, `Buss. Date`, `Status`
    """
    parser = _SimpleHTMLTableParser()
    parser.feed(html_or_text)
    parsed_rows: list[dict[str, str]] = []

    for row in parser.rows:
        if len(row) < 2:
            continue
        first_col = row[0].strip()
        if first_col.lower() in {"id", "sap", "sap code", "store id"}:
            continue
        code_match = re.search(r"\b(\d{4})\b", first_col)
        if not code_match:
            continue
        branch_code = code_match.group(1)
        store_name = row[1].strip() if len(row) > 1 else branch_code
        region = row[2].strip() if len(row) > 2 else "Cairo"
        last_trans = row[3].strip() if len(row) > 3 else "—"
        buss_date = row[4].strip() if len(row) > 4 else "—"
        status_val = row[5].strip() if len(row) > 5 else "Not Updated"
        norm_status = (
            "Not Updated"
            if "not" in status_val.lower() or "down" in status_val.lower()
            else "Updated"
        )
        parsed_rows.append(
            {
                "branch_code": branch_code,
                "store_name": store_name,
                "region": region,
                "last_trans_raw": last_trans,
                "business_date": buss_date,
                "status": norm_status,
            }
        )
    return parsed_rows


def extract_isp_reference_number(subject: str, body_text: str) -> Optional[str]:
    """Extract ISP Case / Ticket reference number from NOOR, ORANGE, or WE email patterns.

    Patterns from the 65 real `.eml` files in `Info/`:
    - NOOR: `Case No: 244010`, `Case# 243860`, `Ticket update #243876`, `trouble ticket #243881`
    - ORANGE: `ticket number (1-1312322942540 For QID ...)`, `1-13123...`
    - WE: `[Request ID :##RE-8407532##]`, `ref.tt#8407532`, `Ticket: 8400809`
    """
    combined = f"{subject}\n{body_text}"

    # WE Request ID pattern: ##RE-8407532##
    we_match = re.search(r"##RE-(\d+)##", combined, re.IGNORECASE)
    if we_match:
        return we_match.group(1)

    # ORANGE ticket pattern: 1-1312322942540
    orange_match = re.search(r"\b(1-\d{10,15})\b", combined)
    if orange_match:
        return orange_match.group(1)

    # NOOR Case / Ticket pattern: Case No: 244010, Case # 243876, Ticket update #243981
    noor_match = re.search(
        r"(?:case\s*(?:no[_:\s]*|#\s*)|trouble\s*ticket\s*#?\s*|ticket\s*update\s*#\s*|ref\.tt#\s*)(\d{5,9})\b",
        combined,
        re.IGNORECASE,
    )
    if noor_match:
        return noor_match.group(1)

    return None


def extract_branch_sap_code(
    subject: str,
    body_text: str,
    *,
    preferred_branch_code: Optional[str] = None,
) -> Optional[str]:
    """Extract 4-digit Kazyon Branch SAP Code from email subject or body.

    Rules (Gap 3):
    1. Prefer the branch of a correlated ticket (`preferred_branch_code`).
    2. For WE subjects (`Kazyon #E33209 #<LL> #<3G> #<SAP>`), take the last `#`-separated 4-digit token.
    3. Never take 4 digits out of a longer number such as `6181183` or `243981`.
    """
    if preferred_branch_code:
        return preferred_branch_code.strip()

    # Rule 2: WE subject with `#`-separated tokens -> take the last standalone 4-digit token
    we_subject_tokens = re.findall(r"#\s*(?<!\d)([12]\d{3})(?!\d)", subject)
    if we_subject_tokens:
        return we_subject_tokens[-1]

    combined = f"{subject}\n{body_text}"

    # Explicit "store 2009", "branch 1188", "KAZYON - 1904-", or "Kazyon 2027"
    explicit = re.search(
        r"(?:store|branch|kazyon(?:\s*-\s*|\s+))#?\s*(?<!\d)([12]\d{3})(?!\d)",
        combined,
        re.IGNORECASE,
    )
    if explicit:
        return explicit.group(1)

    # Standalone `#1251` in body
    hash_tokens = re.findall(r"#\s*(?<!\d)([12]\d{3})(?!\d)", combined)
    if hash_tokens:
        return hash_tokens[-1]

    # Fallback: standalone 4-digit store code starting with 1 or 2 not part of a longer number or year
    for match in re.finditer(r"(?<![\d-])([12]\d{3})(?!\d)", combined):
        code = match.group(1)
        if code not in {"2024", "2025", "2026"} or f"store {code}" in combined.lower():
            return code
    return None


def extract_site_phone(body_text: str) -> Optional[str]:
    """Extract Egyptian mobile phone number (`010...`, `011...`, `012...`, `015...`) across all replies in the email thread (newest reply first)."""
    if not body_text:
        return None
    for reply in split_email_thread_replies(body_text):
        phone_match = re.search(r"\b(01[0125][\d\s-]{8,11})\b", reply.get("body", ""))
        if phone_match:
            return re.sub(r"\s+", " ", phone_match.group(1)).strip()
    phone_match = re.search(r"\b(01[0125][\d\s-]{8,11})\b", body_text)
    if phone_match:
        return re.sub(r"\s+", " ", phone_match.group(1)).strip()
    return None


def extract_ticket_number_tag(subject: str, body_text: str) -> Optional[str]:
    """Extract `[NET-XXXX]` or `NET-XXXX` ticket correlation tag from subject or body."""
    combined = f"{subject}\n{body_text}"
    match = re.search(r"\b(NET-\d{3,6})\b", combined, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def extract_circuit_id_hint(subject: str, body_text: str) -> Optional[str]:
    """Extract ORANGE (`QUO1-...`) or WE (`6181...`) circuit/order ID from subject or body."""
    combined = f"{subject}\n{body_text}"
    quo_match = re.search(r"\b(QUO1-\d{6,12})\b", combined, re.IGNORECASE)
    if quo_match:
        return quo_match.group(1).upper()
    we_order_match = re.search(r"#\s*(6\d{6})\b", combined)
    if we_order_match:
        return we_order_match.group(1)
    return None


def _clean_quoted_line(line: str) -> str:
    """Strip leading `>` quote markers while preserving indentation."""
    return re.sub(r"^(?:\s*>\s?)+", "", line)


def split_email_thread_replies(body_text: str) -> list[dict[str, Any]]:
    """Parse a full email thread body into individual replies ordered from newest (index 0) to oldest.

    Handles standard thread separators found in Kazyon branch & ISP emails:
    - `On <date>, <author> wrote:` (including wrapped multi-line headers and Arabic locale dates)
    - Outlook header blocks (`From: ...` followed by `Sent:` / `Date:` / `To:` / `Subject:`)
    - `-----Original Message-----` and `________________________________` dividers
    """
    if not body_text or not body_text.strip():
        return []

    normalized = body_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = normalized.split("\n")
    n = len(raw_lines)

    segments: list[tuple[Optional[str], list[str]]] = []
    current_header: Optional[str] = None
    current_lines: list[str] = []

    i = 0
    while i < n:
        cleaned = _clean_quoted_line(raw_lines[i]).strip()
        lower = cleaned.lower()

        # 1. Divider line (`-----Original Message-----` or `________________________________`)
        if lower.startswith("-----original message-----") or re.match(r"^_{10,}$", lower):
            header_parts: list[str] = [cleaned]
            j = i + 1
            while j < n and len(header_parts) < 8:
                next_clean = _clean_quoted_line(raw_lines[j]).strip()
                next_lower = next_clean.lower()
                if not next_clean:
                    if len(header_parts) > 1:
                        j += 1
                        break
                    j += 1
                    continue
                if any(
                    next_lower.startswith(prefix)
                    for prefix in ("from:", "sent:", "date:", "to:", "cc:", "subject:")
                ):
                    header_parts.append(next_clean)
                    j += 1
                else:
                    break
            if "\n".join(current_lines).strip() or current_header:
                segments.append((current_header, current_lines))
            current_header = " | ".join(header_parts)
            current_lines = []
            i = j
            continue

        # 2. Outlook header block starting with `From:`
        if lower.startswith("from:"):
            lookahead = [
                _clean_quoted_line(raw_lines[k]).strip().lower()
                for k in range(i, min(n, i + 6))
                if _clean_quoted_line(raw_lines[k]).strip()
            ]
            has_outlook_meta = ("sent:" in lower or "date:" in lower or "to:" in lower) or any(
                any(lk.startswith(p) for p in ("sent:", "date:", "to:", "cc:", "subject:"))
                for lk in lookahead[1:4]
            )
            if has_outlook_meta:
                header_parts = [cleaned]
                j = i + 1
                while j < n and len(header_parts) < 7:
                    next_clean = _clean_quoted_line(raw_lines[j]).strip()
                    next_lower = next_clean.lower()
                    if not next_clean:
                        j += 1
                        break
                    if any(
                        next_lower.startswith(prefix)
                        for prefix in ("sent:", "date:", "to:", "cc:", "subject:", "importance:")
                    ):
                        header_parts.append(next_clean)
                        j += 1
                    else:
                        break
                if "\n".join(current_lines).strip() or current_header:
                    segments.append((current_header, current_lines))
                current_header = " | ".join(header_parts)
                current_lines = []
                i = j
                continue

        # 3. `On <date>, <sender> wrote:` (single-line or wrapped across up to 3 lines)
        if re.match(r"^on\s+.+wrote:\s*$", lower):
            if "\n".join(current_lines).strip() or current_header:
                segments.append((current_header, current_lines))
            current_header = cleaned
            current_lines = []
            i += 1
            continue

        if lower.startswith("on ") and i + 1 < n:
            combined_two = f"{cleaned} {_clean_quoted_line(raw_lines[i + 1]).strip()}"
            if re.match(r"^on\s+.+wrote:\s*$", combined_two.lower()):
                if "\n".join(current_lines).strip() or current_header:
                    segments.append((current_header, current_lines))
                current_header = combined_two.strip()
                current_lines = []
                i += 2
                continue

        current_lines.append(_clean_quoted_line(raw_lines[i]))
        i += 1

    if "\n".join(current_lines).strip() or current_header:
        segments.append((current_header, current_lines))

    replies: list[dict[str, Any]] = []
    for header, lines in segments:
        body = "\n".join(lines).strip()
        if not body and not header:
            continue
        sender_hint: Optional[str] = None
        sent_at_hint: Optional[str] = None
        if header:
            from_m = re.search(r"From:\s*([^|]+)", header, re.IGNORECASE)
            if from_m:
                sender_hint = from_m.group(1).strip()
            sent_m = re.search(r"(?:Sent|Date):\s*([^|]+)", header, re.IGNORECASE)
            if sent_m:
                sent_at_hint = sent_m.group(1).strip()
            on_m = re.match(r"^On\s+(.+?),\s*(.+?)\s+wrote:\s*$", header, re.IGNORECASE)
            if on_m:
                sent_at_hint = sent_at_hint or on_m.group(1).strip()
                sender_hint = sender_hint or on_m.group(2).strip()

        idx = len(replies)
        replies.append(
            {
                "index": idx,
                "is_latest": idx == 0,
                "header": header or "Latest Reply (Top of Email)",
                "sender_hint": sender_hint,
                "sent_at_hint": sent_at_hint,
                "body": body,
            }
        )

    if not replies:
        return [
            {
                "index": 0,
                "is_latest": True,
                "header": "Latest Reply (Top of Email)",
                "sender_hint": None,
                "sent_at_hint": None,
                "body": normalized.strip(),
            }
        ]
    return replies


def format_thread_replies_for_prompt(
    replies: list[dict[str, Any]],
    prior_db_emails: Optional[list[dict[str, Any]]] = None,
    max_chars: int = 6000,
) -> str:
    """Format all parsed in-body thread replies plus prior database thread emails for the LLM prompt."""
    sections: list[str] = []
    for item in replies:
        idx = item.get("index", 0)
        tag = "LATEST REPLY" if item.get("is_latest") else f"QUOTED REPLY #{idx}"
        hdr = item.get("header") or ""
        body = (item.get("body") or "").strip()
        sections.append(f"[{tag} | {hdr}]\n{body}")

    if prior_db_emails:
        for db_idx, msg in enumerate(prior_db_emails, start=1):
            direction = msg.get("direction", "INBOUND")
            thread_type = msg.get("thread_type", "BRANCH")
            sender = msg.get("sender", "")
            sent_at = msg.get("sent_or_received_at", "")
            subj = msg.get("subject", "")
            b_txt = strip_reply_quotes(msg.get("body_text") or "")[:800]
            sections.append(
                f"[PRIOR TICKET DB MESSAGE #{db_idx} | {direction} {thread_type} | From: {sender} | At: {sent_at} | Subject: {subj}]\n{b_txt}"
            )

    joined = "\n\n---\n\n".join(sections)
    return joined[:max_chars]


def strip_reply_quotes(body_text: str) -> str:
    """Return the latest (top-most) reply text from an email thread so classifiers see the newest turn first."""
    if not body_text:
        return ""
    replies = split_email_thread_replies(body_text)
    if replies and replies[0].get("body"):
        return str(replies[0]["body"]).strip()
    return body_text.strip()


def build_synthetic_eml_bytes(
    *,
    sender: str,
    recipients: list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cc: Optional[list[str]] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[list[str]] = None,
    message_id: Optional[str] = None,
    attachment_filenames: Optional[list[str]] = None,
) -> bytes:
    """Construct valid RFC-5322 `.eml` bytes with thread correlation headers and optional attachments."""
    from email.message import EmailMessage

    msg = EmailMessage()
    mid = message_id or f"<{uuid4().hex[:12]}@kazyon-loop.local>"
    msg["Message-ID"] = mid
    msg["Date"] = email.utils.format_datetime(datetime.now(timezone.utc))
    msg["From"] = sender
    msg["To"] = ", ".join(recipients or ["noc@kazyon.com"])
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)

    msg.set_content(body_text or "(Empty body)")
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    for fname in attachment_filenames or []:
        clean_name = fname.strip()
        if not clean_name:
            continue
        msg.add_attachment(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9",
            maintype="image",
            subtype="jpeg",
            filename=clean_name,
        )

    return msg.as_bytes()
