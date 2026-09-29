from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.errors import PortalError
from backend.scrapers.adangal import client as adangal_client

router = APIRouter(prefix="/api/adangal", tags=["adangal"])


@router.get("/districts")
def districts():
    return adangal_client.fetch_districts()


@router.get("/divisions/{district_id}")
def divisions(district_id: str):
    return adangal_client.fetch_divisions(district_id)


@router.get("/mandals/{district_id}/{division_id}")
def mandals(district_id: str, division_id: str):
    return adangal_client.fetch_mandals(district_id, division_id)


@router.get("/villages/{district_id}/{mandal_id}")
def villages(district_id: str, mandal_id: str):
    return adangal_client.fetch_villages(district_id, mandal_id)


@router.get("/survey-options/{village_id}")
def survey_options(village_id: str, option: str = "surveyNo"):
    return adangal_client.fetch_survey_options(village_id, option)


class AdangalRequest(BaseModel):
    district_id: str
    division_id: str
    mandal_id: str
    village_id: str
    survey_or_khata_value: str
    option: str = "surveyNo"


@router.post("/search")
def search(req: AdangalRequest):
    # NOTE: the location cascade above (districts -> divisions -> mandals ->
    # villages -> survey-options) is confirmed working live end-to-end. This
    # final search submission is wired per the site's confirmed request shape
    # but has NOT yet returned a verified real result in testing (the portal's
    # response consistently looked like an unchanged landing page rather than
    # a results page or a genuine, isolated error, across several debugging
    # attempts) — flagging honestly rather than claiming this is proven.
    try:
        return adangal_client.fetch_adangal(
            district_id=req.district_id,
            division_id=req.division_id,
            mandal_id=req.mandal_id,
            village_id=req.village_id,
            survey_or_khata_value=req.survey_or_khata_value,
            option=req.option,
        )
    except PortalError as exc:
        raise HTTPException(status_code=404 if "No record" in exc.user_message else 502, detail=exc.user_message)
