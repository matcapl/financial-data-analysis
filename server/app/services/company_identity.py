"""company_identity.py

Company identity helpers.

Goal: keep longitudinal data consistent when company names vary.

Current strategy:
- Prefer Companies House number as stable identifier.
- Infer Companies House number from uploaded filename using config/overrides.
- Resolve uploads to an existing company row by CH number when possible.

This is intentionally conservative:
- If we cannot infer a CH number, we do nothing.
- If a conflict exists (CH already assigned), we reuse the existing company.
"""

from __future__ import annotations

from typing import Optional


def infer_companies_house_number_from_filename(filename: str) -> Optional[str]:
    """Best-effort CH number inference using configured company names.

    Uses `config/company_overrides.yaml` (loaded via field_mapper.COMPANY_OVERRIDES).
    """

    if not filename:
        return None

    name = filename.lower()

    try:
        from field_mapper import COMPANY_OVERRIDES

        by_ch = (COMPANY_OVERRIDES or {}).get('companies_house', {})
        if isinstance(by_ch, dict):
            for ch, meta in by_ch.items():
                if not isinstance(meta, dict):
                    continue
                company_name = str(meta.get('name') or '').strip().lower()
                if company_name and company_name in name:
                    return str(ch)
    except Exception:
        pass

    # Fallback: lightweight known tokenisation patterns
    if 'nfamily' in name or 'n family' in name:
        return '11986090'

    return None


def resolve_company_id_for_upload(conn, *, company_id: int, filename: str) -> int:
    """Resolve an upload to a stable company_id using Companies House number.

    - If we can infer a CH number from filename and that CH exists on another company row,
      return that company id.
    - If we can infer a CH number and the current company row has no CH number, attach it.
    - Otherwise return the provided company_id.

    Expects a psycopg2 connection.
    """

    ch = infer_companies_house_number_from_filename(filename)
    if not ch:
        return company_id

    try:
        with conn.cursor() as cur:
            # If there is already a canonical company for this CH number, use it.
            cur.execute(
                "SELECT id FROM companies WHERE companies_house_number = %s LIMIT 1",
                (str(ch),),
            )
            r = cur.fetchone()
            if r and r[0]:
                return int(r[0])

            # Otherwise, attach it to the provided company row if safe.
            cur.execute(
                "SELECT companies_house_number FROM companies WHERE id = %s",
                (company_id,),
            )
            r2 = cur.fetchone()
            current_ch = r2[0] if r2 else None
            if not current_ch:
                cur.execute(
                    "UPDATE companies SET companies_house_number = %s WHERE id = %s",
                    (str(ch), company_id),
                )
                conn.commit()
                return company_id

    except Exception:
        # Best-effort; do not break uploads on identity errors.
        return company_id

    return company_id
