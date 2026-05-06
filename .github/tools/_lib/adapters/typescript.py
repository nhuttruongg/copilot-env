"""TypeScript and TSX tree-sitter adapter."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class TypeScriptAdapter(Adapter):
    def __init__(self, language: str = "typescript"):
        if language not in ("typescript", "tsx", "javascript"):
            raise ValueError(language)
        self._lang = language

    @property
    def language(self) -> str:
        return self._lang

    def extract(self, source: bytes, path: str) -> Extracted:
        parser = get_parser(self._lang)
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
        elif t == "class_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="class",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            for ch in node.children:
                self._walk(ch, src, out, scope + [name])
            return
        elif t in ("method_definition", "method_signature"):
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            caller = ".".join(scope + [name])
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "function_declaration":
            name = self._field_text(node, "name", src)
            out.symbols.append(Symbol(
                name=name, kind="func",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=".".join(scope + [name]),
                signature=self._signature(node, src),
            ))
            caller = ".".join(scope + [name])
            for ch in node.children:
                self._walk_calls(ch, src, out, caller)
            return
        elif t == "lexical_declaration":
            for ch in node.children:
                if ch.type == "variable_declarator":
                    name_node = ch.child_by_field_name("name")
                    val_node = ch.child_by_field_name("value")
                    if name_node and val_node and val_node.type in ("arrow_function", "function_expression"):
                        name = self._text(name_node, src)
                        out.symbols.append(Symbol(
                            name=name, kind="func",
                            start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                            qualified_name=".".join(scope + [name]),
                            signature=self._text(ch, src).split("\n")[0].strip(),
                        ))
        for ch in node.children:
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

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _field_text(self, node, field: str, src: bytes) -> str:
        n = node.child_by_field_name(field)
        return self._text(n, src) if n else ""

    def _signature(self, node, src: bytes) -> str:
        text = self._text(node, src).splitlines()[0] if self._text(node, src) else ""
        return text.strip()

    def _import(self, node, src: bytes, out: Extracted) -> None:
        source_node = node.child_by_field_name("source")
        mod = self._text(source_node, src).strip("'\"") if source_node else ""
        clause = None
        for ch in node.children:
            if ch.type == "import_clause":
                clause = ch
                break
        if clause is None:
            out.imports.append(Import(to_module=mod, line=node.start_point[0] + 1))
            return
        for ch in clause.children:
            if ch.type == "named_imports":
                for spec in ch.children:
                    if spec.type == "import_specifier":
                        name = spec.child_by_field_name("name")
                        alias = spec.child_by_field_name("alias")
                        out.imports.append(Import(
                            to_module=mod,
                            imported=self._text(name, src) if name else "",
                            alias=self._text(alias, src) if alias else "",
                            line=node.start_point[0] + 1,
                        ))
            elif ch.type == "namespace_import":
                ident = ch.children[-1] if ch.children else None
                out.imports.append(Import(
                    to_module=mod,
                    alias=self._text(ident, src) if ident else "",
                    line=node.start_point[0] + 1,
                ))
            elif ch.type == "identifier":
                out.imports.append(Import(
                    to_module=mod,
                    imported="default",
                    alias=self._text(ch, src),
                    line=node.start_point[0] + 1,
                ))
