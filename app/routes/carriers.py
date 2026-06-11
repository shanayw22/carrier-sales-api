import httpx
from fastapi import APIRouter, HTTPException, Query

from app.config import FMCSA_API_KEY, FMCSA_BASE_URL


router = APIRouter(prefix="/carriers", tags=["carriers"])


@router.get("")
async def get_carrier(
    mc_number: str | None = Query(default=None, description="MC Number to look up")
):
    if not mc_number:
        raise HTTPException(status_code=400, detail={"error": "mc_number is required"})

    url = f"{FMCSA_BASE_URL}/{mc_number}?webKey={FMCSA_API_KEY}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        content = data.get("content") or {}
        carrier = content.get("carrier") or {}
        if not carrier:
            raise HTTPException(
                status_code=404,
                detail={"error": "Carrier not found", "mc_number": mc_number},
            )

        return {
            "mc_number": mc_number,
            "legal_name": carrier.get("legalName", ""),
            "dba_name": carrier.get("dbaName", ""),
            "dot_number": carrier.get("dotNumber", ""),
            "allowed_to_operate": carrier.get("allowedToOperate", ""),
            "status_code": carrier.get("statusCode", ""),
            "carrier_operation": carrier.get("carrierOperation", {}).get(
                "carrierOperationDesc", ""
            ),
            "phone": carrier.get("phyPhone", ""),
            "city": carrier.get("phyCity", ""),
            "state": carrier.get("phyState", ""),
        }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={
                "error": f"FMCSA API returned {exc.response.status_code}",
                "mc_number": mc_number,
            },
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc