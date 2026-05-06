"""Java tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class JavaAdapter(Adapter):
    @property
    def language(self) -> str:
        return "java"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("java")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_declaration":
            scoped = node.children[1] if len(node.children) > 1 else None
            if scoped is not None:
                out.imports.append(Import(
                    to_module=self._text(scoped, src),
                    line=node.start_point[0] + 1,
                ))
        elif t == "class_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]), signature=self._line(node, src),
            ))
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t == "method_declaration":
            name = self._field_text(node, "name", src)
            qual = ".".join(scope + [name])
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "method_invocation":
            name_node = node.child_by_field_name("name")
            obj = node.child_by_field_name("object")
            callee = ""
            if obj is not None:
                callee = self._text(obj, src) + "." + self._text(name_node, src)
            elif name_node is not None:
                callee = self._text(name_node, src)
            if callee:
                out.calls.append(Call(caller_name=caller, callee_name=callee,
                                      line=node.start_point[0] + 1))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
