from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Base for all domain models. Mutable, lenient on unknown fields (old saves keep loading)."""

    model_config = ConfigDict(extra="ignore")


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value
