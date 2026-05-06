"""Go tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class GoAdapter(Adapter):
    @property
    def language(self) -> str:
        return "go"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("go")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_declaration":
            self._imports(node, src, out)
        elif t == "type_declaration":
            for ch in node.children:
                if ch.type == "type_spec":
                    name = self._field_text(ch, "name", src)
                    out.symbols.append(Symbol(
                        name=name, kind="type",
                        start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                        qualified_name=name, signature=self._line(ch, src),
                    ))
        elif t == "function_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="func",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=name, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=name)
            return
        elif t == "method_declaration":
            recv = node.child_by_field_name("receiver")
            name = self._field_text(node, "name", src)
            qual = self._receiver_type(recv, src) + "." + name if recv else name
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        for ch in node.children:
            if t in ("function_declaration", "method_declaration"):
                continue
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is not None:
                out.calls.append(Call(
                    caller_name=caller,
                    callee_name=self._text(fn, src),
                    line=node.start_point[0] + 1,
                ))
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    def _imports(self, node, src: bytes, out: Extracted) -> None:
        for ch in node.children:
            if ch.type == "import_spec":
                self._import_spec(ch, src, out)
            elif ch.type == "import_spec_list":
                for spec in ch.children:
                    if spec.type == "import_spec":
                        self._import_spec(spec, src, out)

    def _import_spec(self, spec, src: bytes, out: Extracted) -> None:
        name_node = spec.child_by_field_name("name")
        path_node = spec.child_by_field_name("path")
        path = self._text(path_node, src).strip('"') if path_node else ""
        alias = self._text(name_node, src) if name_node else ""
        out.imports.append(Import(to_module=path, alias=alias, line=spec.start_point[0] + 1))

    def _receiver_type(self, recv_node, src: bytes) -> str:
        for ch in recv_node.children:
            if ch.type == "parameter_declaration":
                tnode = ch.child_by_field_name("type")
                if tnode is not None:
                    return self._text(tnode, src).lstrip("*")
        return ""

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
