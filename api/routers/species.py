# api/routers/species.py

"""
Species requirements endpoints for the Reptilia API.
"""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import SpeciesRequirementsResponse
from api.models.enums import ReptileSpecies

router = APIRouter(prefix="/species", tags=["Species"])


@router.get("", response_model=list[SpeciesRequirementsResponse])
def list_species(db: Database = Depends(get_db)):
    """List all supported species and their requirements."""
    species = list(db.habitat_requirements.find({}))
    return [_doc_to_response(s) for s in species]


@router.get("/{species}", response_model=SpeciesRequirementsResponse)
def get_species_requirements(species: ReptileSpecies, db: Database = Depends(get_db)):
    """Get requirements for a specific species."""
    requirements = db.habitat_requirements.find_one({"species": species.value})
    if not requirements:
        raise HTTPException(status_code=404, detail=f"Species {species.value} not found")
    return _doc_to_response(requirements)


def _doc_to_response(doc: dict) -> SpeciesRequirementsResponse:
    """Convert MongoDB document to response model."""
    return SpeciesRequirementsResponse(
        species=ReptileSpecies(doc["species"]),
        basking_temp_min=doc["basking_temp_min"],
        basking_temp_max=doc["basking_temp_max"],
        cool_side_temp_min=doc["cool_side_temp_min"],
        cool_side_temp_max=doc["cool_side_temp_max"],
        night_temp_min=doc["night_temp_min"],
        night_temp_max=doc["night_temp_max"],
        humidity_min=doc["humidity_min"],
        humidity_max=doc["humidity_max"],
        uvb_required=doc.get("uv_required", False),
        substrate_type=doc.get("substrate_type"),
        notes=doc.get("notes")
    )
