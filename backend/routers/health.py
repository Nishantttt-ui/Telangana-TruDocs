from fastapi import APIRouter

from backend.core.hierarchy import _adangal, _pattadar, _survey_map

router = APIRouter()


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "hierarchy": {
            "pattadar_villages": len(_pattadar()),
            "adangal_villages": len(_adangal()),
            "survey_map_villages": len(_survey_map()),
        },
    }
