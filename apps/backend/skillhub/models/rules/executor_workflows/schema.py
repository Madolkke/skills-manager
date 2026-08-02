from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ExecutorValueType = Literal["string", "integer", "number", "boolean"]
ExecutorScalar = str | int | float | bool | None


class ExecutorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ExecutorValue(ExecutorModel):
    name: str
    description: str
    value: ExecutorScalar
    type: ExecutorValueType


class ExecutorTransition(ExecutorModel):
    id: int
    target_type: Literal["step", "conclusion"]
    target_id: int
    condition: str
    description: str


class ExecutorCollection(ExecutorModel):
    id: int
    kind: Literal["command"]
    command: str
    example_outputs: list[ExecutorScalar]
    inputs: list[ExecutorValue]
    outputs: list[ExecutorValue]


class ExecutorStep(ExecutorModel):
    id: int
    name: str
    condition: str
    collections: list[ExecutorCollection]
    transitions: list[ExecutorTransition]


class ExecutorConclusion(ExecutorModel):
    id: int
    conclusion: str


class ExecutorWorkflow(ExecutorModel):
    id: int
    name: str
    start_step_ids: list[int]
    inputs: list[ExecutorValue]
    steps: list[ExecutorStep]
    conclusions: list[ExecutorConclusion]


__all__ = [
    "ExecutorCollection",
    "ExecutorConclusion",
    "ExecutorScalar",
    "ExecutorStep",
    "ExecutorTransition",
    "ExecutorValue",
    "ExecutorValueType",
    "ExecutorWorkflow",
]
