"""Typed domain models for MFA chain orchestration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FactorDefinition(BaseModel):
    """Represents one available MFA factor in a policy."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: str = Field(min_length=1)


class Policy(BaseModel):
    """Defines orchestration rules used to create session factor sequences."""

    mode: Literal["fixed", "random"]
    required_steps: int = Field(ge=1)
    factors: list[FactorDefinition] = Field(min_length=1)

    @field_validator("factors")
    @classmethod
    def ensure_unique_factor_ids(cls, factors: list[FactorDefinition]) -> list[FactorDefinition]:
        ids = [factor.id for factor in factors]
        if len(ids) != len(set(ids)):
            raise ValueError("factor ids must be unique")
        return factors

    @model_validator(mode="after")
    def validate_required_steps(self) -> "Policy":
        if self.required_steps > len(self.factors):
            raise ValueError("required_steps cannot exceed number of factors")
        return self


class Result(BaseModel):
    """Verification response for each step in the active chain."""

    success: bool
    is_complete: bool
    next_factor_label: str
