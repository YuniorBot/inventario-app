from dataclasses import dataclass, field
from html import escape, unescape
from html.parser import HTMLParser

import bleach
from markupsafe import Markup


ALLOWED_RICH_TEXT_TAGS = {
    "b",
    "br",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "u",
    "ul",
}


def sanitize_rich_text(value: str | None) -> str:
    cleaned = bleach.clean(
        "" if value is None else str(value),
        tags=ALLOWED_RICH_TEXT_TAGS,
        attributes={},
        strip=True,
        strip_comments=True,
    )
    return cleaned.strip()


def rich_text_has_content(value: str | None) -> bool:
    cleaned = sanitize_rich_text(value)
    plain_text = bleach.clean(cleaned, tags=set(), strip=True)
    return bool(unescape(plain_text).replace("\xa0", " ").strip())


def rich_text_markup(value: str | None) -> Markup:
    cleaned = sanitize_rich_text(value)
    return Markup(cleaned.replace("\r\n", "\n").replace("\n", "<br>"))


def rich_text_to_reportlab(value: str | None) -> str:
    parts = []
    for block in rich_text_to_reportlab_blocks(value):
        if block.kind == "paragraph":
            parts.append(block.content)
        elif block.kind == "spacer":
            parts.append("")
        else:
            marker = "&#8226;" if block.kind == "unordered_list" else None
            items = [
                f"{marker or f'{index}.'} {item}"
                for index, item in enumerate(block.items, start=1)
            ]
            parts.append("<br/>".join(items))
    return "<br/><br/>".join(parts)


@dataclass(frozen=True)
class ReportLabRichTextBlock:
    kind: str
    content: str = ""
    items: tuple[str, ...] = ()


def rich_text_to_reportlab_blocks(
    value: str | None,
) -> list[ReportLabRichTextBlock]:
    parser = _RichTextTreeParser()
    parser.feed(sanitize_rich_text(value))
    parser.close()
    return _nodes_to_blocks(parser.nodes)


@dataclass
class _RichTextNode:
    tag: str
    children: list[str | "_RichTextNode"] = field(default_factory=list)


class _RichTextTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[str | _RichTextNode] = []
        self._stack = [self.nodes]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _RichTextNode(tag)
        self._stack[-1].append(node)
        if tag != "br":
            self._stack.append(node.children)

    def handle_endtag(self, tag: str) -> None:
        if tag != "br" and len(self._stack) > 1:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        self._stack[-1].append(data)


def _nodes_to_blocks(
    nodes: list[str | _RichTextNode],
) -> list[ReportLabRichTextBlock]:
    blocks = []
    inline_nodes: list[str | _RichTextNode] = []

    def flush_inline_nodes() -> None:
        if not inline_nodes:
            return
        content = _render_inline(inline_nodes)
        if _nodes_have_content(inline_nodes):
            blocks.append(ReportLabRichTextBlock("paragraph", content=content))
        inline_nodes.clear()

    for node in nodes:
        if isinstance(node, _RichTextNode) and node.tag == "p":
            flush_inline_nodes()
            content = _render_inline(node.children)
            kind = "paragraph" if _nodes_have_content(node.children) else "spacer"
            blocks.append(ReportLabRichTextBlock(kind, content=content))
        elif isinstance(node, _RichTextNode) and node.tag in {"ul", "ol"}:
            flush_inline_nodes()
            items = tuple(
                _render_inline(child.children)
                for child in node.children
                if isinstance(child, _RichTextNode)
                and child.tag == "li"
                and _nodes_have_content(child.children)
            )
            if items:
                kind = "ordered_list" if node.tag == "ol" else "unordered_list"
                blocks.append(ReportLabRichTextBlock(kind, items=items))
        else:
            inline_nodes.append(node)

    flush_inline_nodes()
    while blocks and blocks[0].kind == "spacer":
        blocks.pop(0)
    while blocks and blocks[-1].kind == "spacer":
        blocks.pop()
    return blocks


def _render_inline(nodes: list[str | _RichTextNode]) -> str:
    parts = []
    tag_map = {"b": "b", "strong": "b", "em": "i", "i": "i", "u": "u"}
    for node in nodes:
        if isinstance(node, str):
            normalized = node.replace("\r\n", "\n").replace("\r", "\n")
            parts.append("<br/>".join(escape(part) for part in normalized.split("\n")))
            continue
        if node.tag == "br":
            parts.append("<br/>")
            continue
        reportlab_tag = tag_map.get(node.tag)
        content = _render_inline(node.children)
        if reportlab_tag:
            parts.append(f"<{reportlab_tag}>{content}</{reportlab_tag}>")
        elif node.tag in {"ul", "ol"}:
            marker = "&#8226;" if node.tag == "ul" else None
            items = [
                _render_inline(child.children)
                for child in node.children
                if isinstance(child, _RichTextNode) and child.tag == "li"
            ]
            parts.append(
                "<br/>".join(
                    f"{marker or f'{index}.'} {item}"
                    for index, item in enumerate(items, start=1)
                )
            )
        else:
            parts.append(content)
    return "".join(parts)


def _nodes_have_content(nodes: list[str | _RichTextNode]) -> bool:
    for node in nodes:
        if isinstance(node, str):
            if unescape(node).replace("\xa0", " ").strip():
                return True
        elif node.tag != "br" and _nodes_have_content(node.children):
            return True
    return False
