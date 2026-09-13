from html import escape, unescape
from html.parser import HTMLParser

import bleach
from markupsafe import Markup


ALLOWED_RICH_TEXT_TAGS = {
    "br",
    "em",
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
    parser = _ReportLabRichTextParser()
    parser.feed(sanitize_rich_text(value))
    parser.close()
    return parser.result()


class _ReportLabRichTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.lists: list[dict[str, int | str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "strong":
            self.parts.append("<b>")
        elif tag == "em":
            self.parts.append("<i>")
        elif tag == "u":
            self.parts.append("<u>")
        elif tag == "br":
            self._line_break()
        elif tag == "p":
            self._paragraph_break()
        elif tag in {"ul", "ol"}:
            self._paragraph_break()
            self.lists.append({"tag": tag, "index": 0})
        elif tag == "li":
            self._line_break()
            if self.lists and self.lists[-1]["tag"] == "ol":
                self.lists[-1]["index"] = int(self.lists[-1]["index"]) + 1
                self.parts.append(f'{self.lists[-1]["index"]}. ')
            else:
                self.parts.append("&#8226; ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "strong":
            self.parts.append("</b>")
        elif tag == "em":
            self.parts.append("</i>")
        elif tag == "u":
            self.parts.append("</u>")
        elif tag == "p":
            self._paragraph_break()
        elif tag in {"ul", "ol"}:
            if self.lists:
                self.lists.pop()
            self._paragraph_break()

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))

    def result(self) -> str:
        result = "".join(self.parts)
        while result.endswith("<br/>"):
            result = result[:-5]
        return result

    def _line_break(self) -> None:
        if self.parts and not self.parts[-1].endswith("<br/>"):
            self.parts.append("<br/>")

    def _paragraph_break(self) -> None:
        if not self.parts:
            return
        if self.parts[-1].endswith("<br/><br/>"):
            return
        if self.parts[-1].endswith("<br/>"):
            self.parts.append("<br/>")
        else:
            self.parts.append("<br/><br/>")
