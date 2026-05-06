"""C and C++ tree-sitter adapter (sibling languages share a walker)."""
from __future__ import annotations
from .base import Adapter, Extracted, Symbol, Import, Call
from . import get_parser


class CCppAdapter(Adapter):
    def __init__(self, language: str = "c"):
        if language not in ("c", "cpp"):
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
        if t == "preproc_include":
            for ch in node.children:
                if ch.type in ("string_literal", "system_lib_string"):
                    inc = self._text(ch, src).strip('<>"')
                    out.imports.append(Import(to_module=inc, line=node.start_point[0] + 1))
        elif t == "function_definition":
            decl = node.child_by_field_name("declarator")
            name = self._declarator_name(decl, src) if decl else ""
            qual = ".".join(scope + [name]) if name else ""
            out.symbols.append(Symbol(
                name=name, kind="func" if not scope else "method",
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                qualified_name=qual, signature=self._line(node, src),
            ))
            self._walk_calls(node, src, out, caller=qual)
            return
        elif t in ("class_specifier", "struct_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = self._text(name_node, src)
                out.symbols.append(Symbol(
                    name=name, kind="class" if t == "class_specifier" else "type",
                    start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    qualified_name=".".join(scope + [name]), signature=self._line(node, src),
                ))
                for ch in node.children:
                    self._walk(ch, src, out, scope + [name])
                return
        elif t == "namespace_definition":
            name_node = node.child_by_field_name("name")
            ns = self._text(name_node, src) if name_node else ""
            for ch in node.children:
                self._walk(ch, src, out, scope + [ns] if ns else scope)
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

    def _declarator_name(self, node, src: bytes) -> str:
        cur = node
        while cur is not None:
            if cur.type == "identifier" or cur.type == "field_identifier":
                return self._text(cur, src)
            decl = cur.child_by_field_name("declarator")
            if decl is None:
                for ch in cur.children:
                    if ch.type in ("identifier", "field_identifier", "qualified_identifier"):
                        return self._text(ch, src)
                return ""
            cur = decl
        return ""

    @staticmethod
    def _text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    def _line(self, node, src: bytes) -> str:
        return self._text(node, src).splitlines()[0].strip() if self._text(node, src) else ""
