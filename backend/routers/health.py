from fastapi import APIRouter

from backend.core.hierarchy import _adangal, _pattadar

router = APIRouter()


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "hierarchy": {
            "pattadar_villages": len(_pattadar()),
            "adangal_villages": len(_adangal()),
        },
    }
