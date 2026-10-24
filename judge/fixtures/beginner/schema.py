"""Data contract for executable authored exercise fixtures."""
from typing import Callable, TypedDict


class Sample(TypedDict):
    input: str
    output: str
    explanation: str


class ProblemSpec(TypedDict):
    code: str
    title: str
    section: str
    group: str
    tags: list[str]
    nodes: list[str]
    statement: str
    samples: list[Sample]
    explanation: str
    complexity: str
    cpp: str
    cases: list[str]
    oracle: Callable[[str], str]
    function_practice: bool
