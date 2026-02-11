# TODO — Company Identity (Companies House)

Date: 2026-01-25

## Goal
Attach each uploaded document and resulting facts to a stable, canonical company identity so longitudinal data stays consistent even when names vary.

## Near-term (manual)
- Manually set `companies.companies_house_number` for the active company.
- For nFamily:
  - Companies House number: `11986090`

## TODO (automated lookup; placeholder)
- Implement Companies House number lookup from:
  - company name in pack cover/header/footer
  - Companies House PDF accounts (when provided)
  - user-confirmed selection (hybrid: auto-suggest → user confirms)

Notes:
- Do **not** auto-assign an identifier without user confirmation.
- Store the chosen identifier on the `companies` row and copy into `documents.metadata` for traceability.
