import hashlib
import base64
import json
import pdb
from typing import Any

def _build_c(e: Any, a: Any) -> str:
    c = str(e)
    if isinstance(a, (dict, list)):
        c += json.dumps(a, separators=(",", ":"), ensure_ascii=False)
    elif isinstance(a, str):
        c += a
    return c


def _md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


async def seccore_signv2(
    page,
    e: Any,
    a: Any,
) -> str:
    c = _build_c(e, a)
    d = _md5_hex(c)

    s = await page.evaluate("(c, d) => window.mnsv2(c, d)", c, d)
    f = {
        "x0": "4.2.6",
        "x1": "xhs-pc-web",
        "x2": "Mac OS",
        "x3": s,
        "x4": a,
    }
    payload = json.dumps(f, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = "XYS_" + base64.b64encode(payload).decode("ascii")
    return token