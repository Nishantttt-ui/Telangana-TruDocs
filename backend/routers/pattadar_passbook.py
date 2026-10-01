from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.errors import PortalError
from backend.scrapers.pattadar_passbook import client as pattadar_client

router = APIRouter(prefix="/api/pattadar", tags=["pattadar"])


@router.get("/districts")
def districts():
    return pattadar_client.fetch_districts()


@router.get("/mandals/{district_id}")
def mandals(district_id: str):
    return pattadar_client.fetch_mandals(district_id)


@router.get("/villages/{mandal_id}")
def villages(mandal_id: str):
    return pattadar_client.fetch_villages(mandal_id)


@router.get("/survey-options/{village_id}")
def survey_options(village_id: str):
    return pattadar_client.fetch_survey_options(village_id)


@router.get("/khata-options/{village_id}")
def khata_options(village_id: str, survey_no: str):
    return pattadar_client.fetch_khata_options(village_id, survey_no)


class PattadarRequest(BaseModel):
    district_id: str
    mandal_id: str
    village_id: str
    survey_no: str
    khata_id: str


@router.post("/search")
def search(req: PattadarRequest):
    try:
        return pattadar_client.fetch_pattadar_by_survey(
            district_id=req.district_id,
            mandal_id=req.mandal_id,
            village_id=req.village_id,
            survey_no=req.survey_no,
            khata_id=req.khata_id,
        )
    except PortalError as exc:
        raise HTTPException(status_code=404 if "No record" in exc.user_message else 502, detail=exc.user_message)
