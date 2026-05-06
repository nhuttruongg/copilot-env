"""Adapter base class + extracted-data dataclasses."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Symbol:
    name: str
    kind: str            # func | class | method | var | type | const
    start_line: int
    end_line: int
    qualified_name: str = ""
    signature: str = ""
    docstring: str = ""
    visibility: str = "public"


@dataclass
class Import:
    to_module: str
    imported: str = ""
    alias: str = ""
    line: int = 0


@dataclass
class Call:
    caller_name: str   # qualified name of the enclosing symbol; "" if module-level
    callee_name: str
    line: int = 0


@dataclass
class Ref:
    symbol_name: str
    line: int
    kind: str = "read"


@dataclass
class Extracted:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)


class Adapter(ABC):
    """Per-language extractor. Stateless and thread-safe."""

    @property
    @abstractmethod
    def language(self) -> str: ...

    @abstractmethod
    def extract(self, source: bytes, path: str) -> Extracted:
        """Parse source bytes and return extracted symbols/imports/calls/refs."""
