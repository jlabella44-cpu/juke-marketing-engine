from typing import Literal

from pydantic import BaseModel, Field

VALID_ROOM_TAGS = Literal[
    "exterior", "kitchen", "living_room", "dining",
    "primary_bedroom", "primary_bathroom", "bedroom",
    "bathroom", "office", "basement", "outdoor_living",
    "garage", "laundry", "entryway", "staircase", "drone", "detail", "other"
]

VALID_STANDOUT_FEATURES = Literal[
    "pool", "water_view", "acreage", "vaulted_ceilings",
    "luxury_kitchen", "outdoor_kitchen", "barn", "shop", "theater", "gym"
]


class TaggingResult(BaseModel):
    image_index: int
    room_tag: VALID_ROOM_TAGS
    feature_tags: list[str] = []
    ai_score: float = Field(ge=0.0, le=1.0)
    is_drone: bool = False
    standout_features: list[VALID_STANDOUT_FEATURES] = []
