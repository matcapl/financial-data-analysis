from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.reconciliation_engine import run_reconciliation

router = APIRouter(prefix="/api", tags=["reconciliation"])


class ReconcileRequest(BaseModel):
    company_id: int
    document_id: int | None = None
    clear_existing: bool = True


@router.post("/reconcile")
async def reconcile(request: ReconcileRequest):
    if request.company_id <= 0:
        raise HTTPException(status_code=400, detail="company_id must be positive")

    result = run_reconciliation(
        company_id=request.company_id,
        document_id=request.document_id,
        clear_existing=request.clear_existing,
    )
    return result
