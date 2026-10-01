from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Message:
    role: str
    content: Any


@dataclass(frozen=True)
class Usage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass(frozen=True)
class GatewayResult:
    text: str
    provider: str
    requested_model: str
    returned_model: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Usage] = None
    tool_calls: list = field(default_factory=list)


@dataclass(frozen=True)
class GatewayEvent:
    type: str
    text: str = ''
    tool_call: Optional[dict] = None
    result: Optional[GatewayResult] = None


@dataclass(frozen=True)
class ModelCatalog:
    """Distinct model/combo IDs returned by the provider, without raw metadata."""

    ids: tuple[str, ...]

    def __len__(self):
        return len(self.ids)

    def contains(self, model_id):
        return model_id in self.ids
