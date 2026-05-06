"""Python tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class PythonAdapter(Adapter):
    @property
    def language(self) -> str:
        return "python"

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser("python")
        if parser is None:
            return Extracted()
        tree = parser.parse(source)
        out = Extracted()
        self._walk(tree.root_node, source, out, scope=[])
        return out

    def _walk(self, node, src: bytes, out: Extracted, scope: list[str]) -> None:
        t = node.type
        if t == "import_statement":
            self._import(node, src, out)
        elif t == "import_from_statement":
            self._import_from(node, src, out)
        elif t == "class_definition":
            name = self._field_text(node, "name", src)
            sym = Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
                docstring=self._docstring(node, src),
            )
            out.symbols.append(sym)
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t == "function_definition":
            name = self._field_text(node, "name", src)
            kind = "method" if scope else "func"
            sym = Symbol(
                name=name, kind=kind,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
                docstring=self._docstring(node, src),
                visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            )
            out.symbols.append(sym)
            caller = sym.qualified_name
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "call":
            self._call(node, src, out, caller="")
        for ch in node.children:
            self._walk(ch, src, out, scope)

    def _walk_calls(self, node, src: bytes, out: Extracted, caller: str) -> None:
        if node.type == "call":
            self._call(node, src, out, caller=caller)
        for ch in node.children:
            self._walk_calls(ch, src, out, caller)

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _signature(self, node, src: bytes) -> str:
        text = self._text(node, src).splitlines()[0] if self._text(node, src) else ""
        return text.strip()

    def _docstring(self, node, src: bytes) -> str:
        body = node.child_by_field_name("body")
        if body is None:
            return ""
        for ch in body.children:
            if not ch.is_named:
                continue  # skip anonymous tokens (newlines, indentation)
            # tree-sitter Python: docstring is a direct string child of block
            if ch.type == "string":
                return self._text(ch, src).strip("\"' \n")
            # older grammar variant: expression_statement wrapping a string
            if ch.type == "expression_statement":
                inner = ch.children[0] if ch.children else None
                if inner and inner.type == "string":
                    return self._text(inner, src).strip("\"' \n")
            return ""  # first named statement is not a docstring
        return ""

    def _import(self, node, src: bytes, out: Extracted) -> None:
        for ch in node.children:
            if ch.type == "dotted_name":
                out.imports.append(Import(to_module=self._text(ch, src), line=ch.start_point[0] + 1))
            elif ch.type == "aliased_import":
                name = ch.child_by_field_name("name")
                alias = ch.child_by_field_name("alias")
                out.imports.append(Import(
                    to_module=self._text(name, src) if name else "",
                    alias=self._text(alias, src) if alias else "",
                    line=ch.start_point[0] + 1,
                ))

    def _import_from(self, node, src: bytes, out: Extracted) -> None:
        mod = node.child_by_field_name("module_name")
        rel_dots = ""
        for ch in node.children:
            if ch.type == "import_prefix":
                rel_dots = self._text(ch, src)
                break
        mod_text = (rel_dots + (self._text(mod, src) if mod else "")) or rel_dots
        for ch in node.children:
            if ch.type == "dotted_name" and ch is not mod:
                out.imports.append(Import(
                    to_module=mod_text,
                    imported=self._text(ch, src),
                    line=ch.start_point[0] + 1,
                ))
            elif ch.type == "aliased_import":
                name = ch.child_by_field_name("name")
                alias = ch.child_by_field_name("alias")
                out.imports.append(Import(
                    to_module=mod_text,
                    imported=self._text(name, src) if name else "",
                    alias=self._text(alias, src) if alias else "",
                    line=ch.start_point[0] + 1,
                ))

    def _call(self, node, src: bytes, out: Extracted, caller: str) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        callee = self._text(fn, src)
        out.calls.append(Call(caller_name=caller, callee_name=callee, line=node.start_point[0] + 1))
