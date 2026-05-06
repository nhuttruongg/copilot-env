"""Rust tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class RustAdapter(Adapter):
    @property
    def language(self) -> str:
        return "rust"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("rust")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "use_declaration":
            self._use(node, src, out)
        elif t == "struct_item":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="type",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]), signature=self._line(node, src),
            ))
        elif t == "function_item":
            name = self._field_text(node, "name", src)
            qual = ".".join(scope + [name])
            kind = "method" if scope else "func"
            out.symbols.append(Symbol(
                name=name, kind=kind,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        elif t == "impl_item":
            type_node = node.child_by_field_name("type")
            type_name = self._text(type_node, src) if type_node else ""
            for ch in node.children:
                self._walk(ch, src, out, scope + [type_name])
            return
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(caller_name=caller, callee_name=self._text(fn, src),
                                      line=node.start_point[0] + 1))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    def _use(self, node, src: bytes, out: Extracted) -> None:
        for ch in node.children:
            if ch.type in ("scoped_identifier", "scoped_use_list", "use_list", "identifier"):
                out.imports.append(Import(
                    to_module=self._text(ch, src),
                    line=node.start_point[0] + 1,
                ))
                break

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
