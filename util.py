def clamp(val: int, max_: int, clamped: int | None = None) -> int:# {{{
    if clamped is None: clamped = max_
    return clamped if val > max_ else val
# }}}

# vim: foldmethod=marker
