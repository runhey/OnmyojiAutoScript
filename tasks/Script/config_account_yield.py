"""Per-profile settings for yielding to a phone or another game client."""

from pydantic import BaseModel, ConfigDict, Field


class AccountYieldSettings(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    enable: bool = Field(default=False, description='account_yield_enable_help')
    pause_minutes: int = Field(
        default=20, ge=1, le=240, strict=True,
        description='account_yield_pause_minutes_help',
    )
