from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.errors import PortalError
from backend.scrapers.ghmc import mutation_client, property_tax_client

router = APIRouter(prefix="/api/ghmc", tags=["ghmc"])


class MutationRequest(BaseModel):
    assessment_number: str


@router.post("/mutation")
def mutation_status(req: MutationRequest):
    try:
        return mutation_client.fetch_mutation_status(req.assessment_number)
    except PortalError as exc:
        raise HTTPException(status_code=404 if "No record" in exc.user_message else 502, detail=exc.user_message)


@router.get("/circles")
def circles():
    return property_tax_client.fetch_circles()


class PropertyTaxRequest(BaseModel):
    circle: str
    ptin: str = ""
    owner_name: str = ""
    door_no: str = ""


@router.post("/property-tax")
def property_tax(req: PropertyTaxRequest):
    try:
        return property_tax_client.fetch_property_tax(
            ptin=req.ptin, owner_name=req.owner_name, door_no=req.door_no, circle=req.circle
        )
    except PortalError as exc:
        raise HTTPException(status_code=404 if "No record" in exc.user_message else 502, detail=exc.user_message)
