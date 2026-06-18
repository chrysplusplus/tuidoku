import curses
import curses.ascii as cascii

from dataclasses import dataclass, KW_ONLY
from typing import Callable, TypeVar

from util import clamp

T = TypeVar('T')

@dataclass(slots = True)
class Key:
    ch: str
    _: KW_ONLY
    ctrl: bool = False
    alt: bool = False
    special: bool = False

@dataclass(slots = True)
class PadView:
    pad: curses.window
    pad_start: tuple[int,int]
    desired_screen_start: tuple[int,int]
    desired_view_size: tuple[int,int]

@dataclass(slots = True)
class WindowDrawState:
    win: curses.window
    on_draw: Callable[[curses.window], bool] | None = None

@dataclass(slots = True)
class Cursor:
    cursor: tuple[int, int]

ChildWindow = tuple[WindowDrawState, PadView | None]

class MainWindow:
    __slots__ = ("_stdscr", "children", "stdcurs")

    def __init__(self, stdscr_: curses.window):
        self._stdscr = stdscr_
        self.children: list[ChildWindow] = []
        self.stdcurs = Cursor((0, 0))

    @property
    def stdscr(self) -> curses.window:
        return self._stdscr

    @property
    def stddraw(self) -> WindowDrawState:
        return WindowDrawState(self.stdscr, self.on_draw)

    def on_draw(self, _) -> bool:
        self.stdscr.erase()
        self.stdscr.noutrefresh()
        for child in self.children:
            windraw_noutrefresh(*child)

        win_move_cursor(self.stdscr, self.stdcurs)
        return False

    def add_child(self, windraw: WindowDrawState, pv: PadView | None = None):
        self.children.append((windraw, pv))

def padview_clamp(pv: PadView) -> tuple[int,int,int,int,int,int]:# {{{
    '''Provides clamped values for pv.refresh() or pv.noutrefresh()'''
    py, px = pv.pad_start
    sy, sx = pv.desired_screen_start
    h, w = pv.desired_view_size
    pmaxy, pmaxx = pv.pad.getmaxyx()
    smaxy = curses.LINES - 1
    smaxx = curses.COLS - 1

    py = clamp(py, pmaxy, 0)
    px = clamp(px, pmaxx, 0)
    h = clamp(clamp(h, pmaxy - py), smaxy)
    w = clamp(clamp(w, pmaxx - px), smaxx)
    sy = clamp(sy, smaxy - h)
    sx = clamp(sx, smaxx - w)
    return py, px, sy, sx, sy + h, sx + w
# }}}

def windraw_noutrefresh(windraw: WindowDrawState, pv: PadView | None = None):# {{{
    assert pv is None or id(windraw.win) == id(pv.pad)
    dorefresh = windraw.on_draw(windraw.win) if windraw.on_draw is not None else True
    if pv is None and dorefresh:
        windraw.win.noutrefresh()
    elif dorefresh:
        windraw.win.noutrefresh(*padview_clamp(pv))
# }}}

def windraw_refresh(windraw: WindowDrawState, pv: PadView | None = None):# {{{
    curses.update_lines_cols()
    windraw_noutrefresh(windraw, pv)
    curses.doupdate()
# }}}

def utf8_len(byte0: int) -> int:# {{{
    '''Return the expected length of a UTF-8 code point in bytes given the first byte

    Note: this function does not decode the code point, nor does it check if the first
    byte is valid; it just naively checks value ranges in the most significant four bits'''
    assert byte0 < 0x100 and byte0 >= 0
    if byte0 < 0x80:
        return 1
    if byte0 < 0xe0:
        return 2
    if byte0 < 0xf0:
        return 3
    else:
        return 4
# }}}

def getkbytes(stdscr: curses.window) -> list[int]:# {{{
    kbytes = []
    key = stdscr.getch()
    while key != -1:
        kbytes.append(key)
        key = stdscr.getch()
    return kbytes
# }}}

def getkbytes_blocking(win: curses.window) -> list[int]:# {{{
    byte0 = win.getch()
    if byte0 > 0x100: return [byte0]
    if byte0 == cascii.ESC:
        return [byte0] + getkbytes_blocking(win)

    kbytes = [byte0]
    i = utf8_len(byte0) - 1
    while i > 0:
        kbytes.append(win.getch())
        i -= 1
    return kbytes
# }}}

def unctrl(byte: int) -> str:# {{{
    return cascii.unctrl(byte)[1]
# }}}

def key_from_bytes(xs: list[int]) -> Key | None:# {{{
    assert len(xs) > 0
    x = xs[0]
    if x > 0x80 and len(xs) == 1:
        return Key(curses.keyname(x), special = True)
    if x > 0x80:
        try:
            return Key(bytes(xs).decode("utf-8"))
        except UnicodeDecodeError:
            return None
    if x == cascii.ESC and cascii.isctrl(xs[1]):
        return Key(unctrl(xs[1]), ctrl = True, alt = True)
    if x == cascii.ESC:
        return Key(chr(xs[1]), alt = True)
    if cascii.isctrl(x):
        return Key(unctrl(x), ctrl = True)
    else:
        return Key(chr(x))
# }}}

def askey(ch: str) -> Key:# {{{
    upper = ch.upper()
    c_m = upper.startswith("C-M-")
    m_c = upper.startswith("M-C-")
    if c_m or m_c:
        return Key(upper[4], ctrl = True, alt = True)
    if upper.startswith("C-"):
        return Key(upper[2], ctrl = True)
    if upper.startswith("M-"):
        return Key(ch[2], alt = True)
    return Key(ch)
# }}}

def win_addlines(win: curses.window, lines: list[str]):# {{{
    maxy, maxx = win.getmaxyx()
    y = 0
    for line in lines:
        win.addstr(y, 0, line[:maxx + 1])
        y += 1
        if y > maxy:
            break
# }}}

def win_move_cursor(win: curses.window, cursor: Cursor):# {{{
    cy, cx = cursor.cursor
    if cy < 0 or cy > curses.LINES - 1 or cx < 0 or cx > curses.COLS - 1:
        curses.curs_set(0)
    else:
        curses.curs_set(1)
        win.move(cy, cx)
# }}}

def start_curses(stdscr: curses.window, init_fn: Callable[[curses.window], None], main_fn: Callable[[MainWindow], T], *args, **kwargs) -> T:# {{{
    init_fn(stdscr)
    stdwin = MainWindow(stdscr)
    return main_fn(stdwin, *args, **kwargs)
# }}}

# vim: foldmethod=marker
