def clamp(val: int, max_: int, clamped: int | None = None) -> int:# {{{
    if clamped is None: clamped = max_
    return clamped if val > max_ else val
# }}}

def pad_text(text: str, padding: int) -> str:# {{{
    pad = " "* padding
    return pad + text + pad
# }}}

def set_cursor_shape():
    print("\033[2 q", end = '')

# vim: foldmethod=marker
