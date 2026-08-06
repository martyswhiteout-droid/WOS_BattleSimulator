import re
from collections import namedtuple
ParsedValue = namedtuple("ParsedValue", "value unit signed")
_PCT = re.compile(r"^([+-]?)(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?%$")
_PCT_NOSYM = re.compile(r"^([+-])(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?$")  # signed ⇒ clearly a bonus value
_INT = re.compile(r"^(\d{1,3}(?:,\d{3})*|\d+)$")

def parse_value(raw):
    raw = (raw or "").strip()
    m = _PCT.match(raw)
    if m:
        v = float((m.group(2)).replace(",", "") + (m.group(3) or ""))
        return ParsedValue(-v if m.group(1) == "-" else v, "pct", m.group(1) != "")
    m = _PCT_NOSYM.match(raw)
    if m:
        v = float((m.group(2)).replace(",", "") + (m.group(3) or ""))
        return ParsedValue(-v if m.group(1) == "-" else v, "pct", True)
    m = _INT.match(raw)
    if m:
        return ParsedValue(float(m.group(1).replace(",", "")), "int", False)
    return None
