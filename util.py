def clamp(val: int, max_: int, clamped: int | None = None) -> int:# {{{
    if clamped is None: clamped = max_
    return clamped if val > max_ else val
# }}}

def set_cursor_shape():
    print("\033[2 q", end = '')

# vim: foldmethod=marker
