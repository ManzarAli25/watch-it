"""Render the bundled pixel-art banner as truecolor half-block terminal text.

Each character cell stacks two image pixels: the upper half (``▀``) takes the top
pixel as its foreground colour, the lower half takes the bottom pixel as the
background colour. Near-white pixels render transparent so the art sits cleanly on
any terminal background.
"""

from __future__ import annotations

from importlib.resources import files

from rich.style import Style
from rich.text import Text

_WHITE_CUTOFF = 236  # pixels brighter than this on all channels drop out


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _transparent(rgb: tuple[int, int, int]) -> bool:
    return min(rgb) >= _WHITE_CUTOFF


def render_banner(max_width: int = 76, max_height: int = 18) -> Text:
    """Return a Rich Text of the banner, fit within (max_width, max_height) cells."""
    from PIL import Image

    asset = files("watch_mcp").joinpath("assets/banner.png")
    with asset.open("rb") as fh:
        img = Image.open(fh).convert("RGB")

    w, h = img.size
    # One char row = two pixel rows, so the vertical pixel budget is 2*max_height.
    scale = min(max_width / w, (max_height * 2) / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    if nh % 2:
        nh += 1
    img = img.resize((nw, nh))
    px = img.load()

    text = Text(no_wrap=True, overflow="crop")
    for y in range(0, nh, 2):
        for x in range(nw):
            top, bot = px[x, y], px[x, y + 1]
            tt, bt = _transparent(top), _transparent(bot)
            if tt and bt:
                text.append(" ")
            elif tt:
                text.append("▄", Style(color=_hex(bot)))
            elif bt:
                text.append("▀", Style(color=_hex(top)))
            else:
                text.append("▀", Style(color=_hex(top), bgcolor=_hex(bot)))
        if y + 2 < nh:
            text.append("\n")
    return text
