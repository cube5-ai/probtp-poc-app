"""
BoundingBox model for spatial coordinates of content layout information
"""
from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    """
    Spatial coordinates for content layout information with normalized coordinates.

    All coordinates are normalized to the range [0.0, 1.0] where:
    - (0, 0) represents the top-left corner of the page/document
    - (1, 1) represents the bottom-right corner of the page/document
    - x and y represent the top-left corner of the bounding box
    - width and height represent the dimensions of the bounding box
    """

    x: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Left coordinate (normalized 0.0-1.0) - horizontal position of the left edge"
    )

    y: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Top coordinate (normalized 0.0-1.0) - vertical position of the top edge"
    )

    width: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Box width (normalized 0.0-1.0) - horizontal span of the bounding box"
    )

    height: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Box height (normalized 0.0-1.0) - vertical span of the bounding box"
    )

    @model_validator(mode='after')
    def validate_bounds(self) -> 'BoundingBox':
        """
        Validate that the bounding box coordinates stay within normalized bounds.

        Ensures that:
        - x + width does not exceed 1.0 (right edge within bounds)
        - y + height does not exceed 1.0 (bottom edge within bounds)
        """
        if self.x + self.width > 1.0:
            raise ValueError(
                f"Bounding box extends beyond right edge: x ({self.x}) + width ({self.width}) = "
                f"{self.x + self.width} > 1.0"
            )

        if self.y + self.height > 1.0:
            raise ValueError(
                f"Bounding box extends beyond bottom edge: y ({self.y}) + height ({self.height}) = "
                f"{self.y + self.height} > 1.0"
            )

        return self

    class Config:
        """Pydantic configuration for BoundingBox model"""
        json_schema_extra = {
            "example": {
                "x": 0.1,
                "y": 0.2,
                "width": 0.8,
                "height": 0.3
            }
        }
