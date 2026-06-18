#!/usr/bin/env python3

"""
# TODO

- implement game controls
- implement puzzle generation
- refactor big number draws to account for padding (current manually set)
- implement undo
- implement more visual mode indicator
- implement line and box guides
"""

import curses
import curses.ascii as cascii

from dataclasses import dataclass, field, KW_ONLY
from itertools import repeat
from typing import Callable

font_l = [# {{{
          ("▐▛▀▜▌", "▐▙▞▜▌", "▐▙▄▟▌"), # 0
          (" ▄█  ", "  █  ", " ▄█▄ "), # 1
          (" █▀█ ", "  ▄▀ ", " █▄▄ "), # 2
          ("▐▛▀▜▌", "  ▝▚▖", "▐▙▄▟▌"), # 3
          (" █▀█ ", "█▄▄█▄", "   █ "), # 4
          (" █▀▀ ", " ▀▀▄ ", " ▄▄▀ "), # 5
          ("▗▞▀▚▖", "▐▙▄▖ ", "▝▚▄▞▘"), # 6
          ("▝▀▀▜▌", "  ▐▌ ", "  █  "), # 7
          ("▗▞▀▚▖", "▗▞▀▚▖", "▝▚▄▞▘"), # 8
          ("▗▞▀▚▖", "▝▚▄▟▌", " ▗▄▞▘"), # 9
          ("     ", "     ", "     ")
          ]# }}}
font_s = [# {{{
        ("0",), # 0
        ("1",), # 1
        ("2",), # 2
        ("3",), # 3
        ("4",), # 4
        ("5",), # 5
        ("6",), # 6
        ("7",), # 7
        ("8",), # 8
        ("9",), # 9
        (" ",)
        ]# }}}
linechars = [#      1    2    3    4    5{{{
             "00", "─", "│",
             "03", "┌", "┐", "└", "┘",
             "08", "├", "┤", "┬", "┴", "┼",
             "14", "═", "║",
             "17", "╒", "╓", "╔",
             "21", "╕", "╖", "╗",
             "25", "╘", "╙", "╚",
             "29", "╛", "╜", "╝",
             "33", "╞", "╟", "╠",
             "37", "╡", "╢", "╣",
             "41", "╤", "╥", "╦",
             "45", "╧", "╨", "╩",
             "49", "╪", "╫", "╬",
             "53", "╭", "╮", "╯", "╰" ]# }}}
L_ew, L_ns                         = linechars[1],  linechars[2]# {{{
L_es, L_sw, L_ne, L_nw             = linechars[4],  linechars[5],  linechars[6],  linechars[7]
L_nes, L_nsw, L_esw, L_new, L_nesw = linechars[9],  linechars[10], linechars[11], linechars[12], linechars[13]
L_EW, L_NS                         = linechars[15], linechars[16]
L_Es, L_eS, L_ES                   = linechars[18], linechars[19], linechars[20]
L_Sw, L_Sw, L_SW                   = linechars[22], linechars[23], linechars[24]
L_nE, L_Ne, L_NE                   = linechars[26], linechars[27], linechars[28]
L_nW, L_Nw, L_NW                   = linechars[30], linechars[31], linechars[32]
L_nEs, L_NeS, L_NES                = linechars[34], linechars[35], linechars[36]
L_nsW, L_NSw, L_NSW                = linechars[38], linechars[39], linechars[40]
L_EsW, L_eSw, L_ESW                = linechars[42], linechars[43], linechars[44]
L_nEW, L_New, L_NEW                = linechars[46], linechars[47], linechars[48]
L_nEsW, L_NeSw, L_NESW             = linechars[50], linechars[51], linechars[52]
C_es, C_sw, C_nw, C_ne             = linechars[54], linechars[55], linechars[56], linechars[57]# }}}

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
class GridCell:
    num: int | None
    notes: tuple[int,...] = tuple()
    provided: bool = False

SUDOKU_MODE_NORMAL = 0
SUDOKU_MODE_NOTE   = 1
SUDOKU_MAX_MODE    = 1

@dataclass(slots = True)
class SudokuGrid:
    grid: list[GridCell]
    cursor: tuple[int, int] = (0, 0)
    use_big_grid: bool = True
    mode: int = 0

@dataclass(slots = True)
class GridDrawState:
    puzzle: SudokuGrid
    pv: PadView
    sy: int

@dataclass(slots = True)
class Cursor:
    cursor: tuple[int, int]

def init_curses(stdscr):# {{{
    curses.raw()
    curses.use_default_colors()

    # init colors
    assert curses.COLOR_PAIRS > 2
    curses.init_pair(1, curses.COLOR_GREEN, -1)

    global ATTR_PROV
    ATTR_PROV = curses.color_pair(1)
# }}}
def clamp(val: int, max_: int, clamped: int | None = None) -> int:# {{{
    if clamped is None: clamped = max_
    return clamped if val > max_ else val
# }}}
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
def grid_from_str(s: str, provided: bool = False) -> SudokuGrid | None:# {{{
    grid = []
    for ch in s:
        if ch == ".":
            grid.append(GridCell(None))

        elif ch.isdigit():
            grid.append(GridCell(int(ch), provided = provided))

    return SudokuGrid(grid) if len(grid) == 81 else None
# }}}
def get_grid_cell(grid: SudokuGrid, ref: tuple[int, int] | str) -> GridCell | None:# {{{
    if isinstance(ref, str): raise NotImplementedError
    elif not isinstance(ref, tuple): raise TypeError(f"Invalid cell reference: {ref}")
    elif len(ref) != 2: raise ValueError(f"Cell reference must have length of 2: {ref}")
    elif type(ref[0]) != int or type(ref[1]) != int: raise TypeError(f"Cell reference values must be ints: {ref}")

    y,x = ref
    if y < 0 or y > 8 or x < 0 or x > 8: return None
    return grid.grid[y * 9 + x]
# }}}
def grid_lines(cell_height, cell_width) -> list[str]:# {{{
    lines = []

    lines.append("{}{}{}".format(
        L_ES,
        L_ESW.join(repeat(L_EsW.join(repeat(L_EW * cell_width, 3)), 3)),
        L_SW))

    for box_row in range(3):
        for row in range(3):
            for y in range(cell_height):
                lines.append("{}{}{}".format(
                    L_NS,
                    L_NS.join(repeat(L_ns.join(repeat(" " * cell_width, 3)), 3)),
                    L_NS))

            if row < 2:
                lines.append("{}{}{}".format(
                    L_NeS,
                    L_NeSw.join(repeat(L_nesw.join(repeat(L_ew * cell_width, 3)), 3)),
                    L_NSw))

        if box_row < 2:
            lines.append("{}{}{}".format(
                L_NES,
                L_NESW.join(repeat(L_nEsW.join(repeat(L_EW * cell_width, 3)), 3)),
                L_NSW))

    lines.append("{}{}{}".format(
        L_NE,
        L_NEW.join(repeat(L_nEW.join(repeat(L_EW * cell_width, 3)), 3)),
        L_NW))

    return lines
# }}}
LARGE_GRID = grid_lines(5, 9)
LARGE_GRID_SIZE = (len(LARGE_GRID), len(LARGE_GRID[0]))
SMALL_GRID = grid_lines(1, 3)
SMALL_GRID_SIZE = (len(SMALL_GRID), len(SMALL_GRID[0]))

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
def stddraw_def_draw(**kwargs) -> Callable[[curses.window], bool]:# {{{
    children = kwargs["children"]
    cursor = kwargs["cursor"]
    def on_draw(win: curses.window) -> bool:
        win.erase()

        win.noutrefresh()
        for child in children:
            windraw_noutrefresh(*child)

        win_move_cursor(win, cursor)
        return False

    return on_draw
# }}}
SUDOKU_GRID_MARGIN = 5
def is_small_screen(prog: dict, reset_fn: Callable[[], None]) -> bool:# {{{
    draw_errmsg = "Screen too small to display grid"
    if SMALL_GRID_SIZE[0] > curses.LINES - SUDOKU_GRID_MARGIN:
        prog["status_fn"] = lambda: draw_errmsg
        prog["sudoku_draw_last_err"] = True
        return True

    if prog.get("sudoku_draw_last_err", False): # reset if resized screen is no longer too small
        reset_fn()
        prog["sudoku_draw_last_err"] = False

    return False
# }}}
ATTR_NORMAL = curses.A_NORMAL
ATTR_PROV = None # initialised by init_curses
def cell_attr(y: int, x: int, cell: GridCell) -> int: # assuming curses attrs are ints{{{
    if cell.provided:
        return ATTR_PROV
    else:
        return ATTR_NORMAL
# }}}
def scale_big_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    return (6 * y + 2, 10 * x + 3)
# }}}
# TODO refactor padding code
def draw_big_grid(win: curses.window, grid_state: GridDrawState):# {{{
    grid_state.pv.desired_view_size = LARGE_GRID_SIZE
    _, w = grid_state.pv.desired_view_size
    grid_state.pv.desired_screen_start = (grid_state.sy, (curses.COLS - w) // 2)

    win_addlines(win, LARGE_GRID)

    cy, cx = grid_state.puzzle.cursor

    for i, cell in enumerate(grid_state.puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_big_grid_coords((y, x))
        if cell.num is None and len(cell.notes) == 0 and (y, x) == (cy, cx):
            for dy in range(5):
                win.addstr(cur_y + dy - 1, cur_x - 1, " " * 7, curses.A_REVERSE)
            continue

        if cell.num is None and len(cell.notes) == 0:
            continue

        attr = cell_attr(y, x, cell)
        attr = attr | curses.A_REVERSE if (y, x) == (cy, cx) else attr
        if cell.num is not None:
            digit = cell.num
            digit_lines = font_l[digit]
            win.addstr(cur_y - 1, cur_x - 1, " " * 7, attr)
            for line_i, line in enumerate(digit_lines):
                win.addstr(cur_y + line_i, cur_x - 1, " " + line + " ", attr)
            win.addstr(cur_y + 3, cur_x - 1, " " * 7, attr)

        else:
            digits = cell.notes
            win.addstr(cur_y - 1, cur_x - 1, " " * 7, attr)
            for line_i in range(3):
                line_digits = []
                for test_num in (3 * line_i + i + 1 for i in range(3)):
                    line_digits.append(str(test_num) if test_num in digits else " ")

                win.addstr(cur_y + line_i, cur_x - 1, " " + " ".join(line_digits) + " ", attr)

            win.addstr(cur_y + 3, cur_x - 1, " " * 7, attr)
# }}}
def scale_small_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    return (2 * y + 1, 4 * x + 2)
# }}}
def draw_small_grid(win: curses.window, grid_state: GridDrawState):# {{{
    grid_state.pv.pad_start = (0, 0)
    sx = (curses.COLS - SMALL_GRID_SIZE[1]) // 2
    grid_state.pv.desired_screen_start = (grid_state.sy, sx)
    grid_state.pv.desired_view_size = SMALL_GRID_SIZE

    win_addlines(win, SMALL_GRID)

    for i, cell in enumerate(grid_state.puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_small_grid_coords((y, x))
        attr = cell_attr(y, x, cell)
        digit = str(cell.num) if cell.num is not None else ' '

        win.addstr(cur_y, cur_x, digit, attr)
# }}}
def sudoku_def_draw(**kwargs) -> Callable[[curses.window], bool]:# {{{
    cursor = kwargs["cursor"]
    def on_draw(win: curses.window) -> bool:
        prog = kwargs['prog']
        pv = kwargs['pv']

        win.erase()
        if is_small_screen(prog, kwargs['reset_statusbar']): return True

        puzzle = prog.get("puzzle", None)
        sy, _ = pv.desired_screen_start
        if puzzle.use_big_grid:
            draw_big_grid(win, GridDrawState(puzzle, pv, sy))
            cursor.cursor = (-1, -1)

        else:
            cy, cx = scale_small_grid_coords(puzzle.cursor)
            draw_small_grid(win, GridDrawState(puzzle, pv, sy))
            sy, sx = pv.desired_screen_start
            cursor.cursor = (cy + sy, cx + sx)

        return True

    return on_draw
# }}}
def sudoku_move_abs_cursor(sudoku: SudokuGrid, *, y: int | None = None, x: int | None = None):# {{{
    oldy, oldx = sudoku.cursor
    sudoku.cursor = (y if y is not None else oldy, x if x is not None else oldx)
# }}}
def sudoku_move_rel_cursor(sudoku: SudokuGrid, *, y: int = 0, x: int = 0) -> bool: # {{{
    '''Returns True if cursor changed, otherwise False'''
    oldy, oldx = sudoku.cursor
    newy = (oldy + y) % 9
    newx = (oldx + x) % 9
    sudoku.cursor = (newy, newx)
    return (oldy, oldx) != (newy, newx)
# }}}
MODE_STRINGS = [# {{{
        "-- NORMAL --", "-- NOTE --" ]# }}}
def sudoku_def_display_mode(sudoku: SudokuGrid) -> Callable[[], str]:# {{{
    return lambda: MODE_STRINGS[clamp(sudoku.mode, SUDOKU_MAX_MODE, 0)]
# }}}
def sudoku_ins(sudoku: SudokuGrid, digit: int):# {{{
    if digit < 1 or digit > 9: return
    cy, cx = sudoku.cursor
    index = 9 * cy + cx

    if sudoku.grid[index].provided: return

    old_num = sudoku.grid[index].num
    old_notes = sudoku.grid[index].notes
    if sudoku.mode == SUDOKU_MODE_NORMAL and digit == old_num:
        sudoku.grid[index].num = None
    elif sudoku.mode == SUDOKU_MODE_NORMAL:
        sudoku.grid[index].num = digit
    elif sudoku.mode == SUDOKU_MODE_NOTE and digit in old_notes:
        sudoku.grid[index].notes = tuple(d for d in old_notes if d != digit)
    elif sudoku.mode == SUDOKU_MODE_NOTE:
        sudoku.grid[index].notes = (*old_notes, digit)
# }}}
def sudoku_del(sudoku: SudokuGrid):# {{{
    cy, cx = sudoku.cursor
    i = 9 * cy + cx
    if sudoku.grid[i].provided: return
    if sudoku.mode == SUDOKU_MODE_NORMAL:
        sudoku.grid[i].num = None
    elif sudoku.mode == SUDOKU_MODE_NOTE:
        sudoku.grid[i].notes = tuple()
# }}}
def sudoku_toggle_note_mode(sudoku: SudokuGrid):# {{{
    sudoku.mode = SUDOKU_MODE_NORMAL if sudoku.mode == SUDOKU_MODE_NOTE else SUDOKU_MODE_NOTE
# }}}
def titlebar_def_draw(**kwargs) -> Callable[[curses.window], bool]:# {{{
    def on_draw(win: curses.window) -> bool:
        win.erase()
        _, maxx = win.getmaxyx()
        text = "SUDOKU"[:maxx + 1]
        win.addstr(0, (maxx - len(text)) // 2, text)
        return True

    return on_draw
# }}}
def statusbar_def_draw(**kwargs) -> Callable[[curses.window], bool]:# {{{
    def on_draw(win: curses.window) -> bool:
        prog = kwargs['prog']
        status_fn = prog.get("status_fn", lambda: "")
        win.mvwin(curses.LINES - 1, 0)
        _, maxx = win.getmaxyx()
        win.erase()
        txt = status_fn()
        win.addstr(txt[:maxx + 1])
        return True

    return on_draw
# }}}
def statusbar_def_reset(**kwargs) -> Callable[[], None]:# {{{
    def on_reset():
        prog = kwargs['prog']
        prog['status_fn'] = prog.get("default_status_fn", None)

    return on_reset
# }}}
def display_screen_size() -> str:# {{{
    return f" {curses.LINES}, {curses.COLS}"
# }}}
EXAMPLE_PUZZLE = "6...5...7 .9.1..3.. 7..6..94. 8..34.1.. ...5.1... ..5.87..9 .68..2..4 ..1..6.9. 3...9...1"

def main(stdscr: curses.window):
    init_curses(stdscr)

    puzzle = grid_from_str(EXAMPLE_PUZZLE, provided = True)

    prog = {
            "default_status_fn": sudoku_def_display_mode(puzzle),
            "sudoku_draw_last_err": False,
            "puzzle": puzzle,
            }
    prog['status_fn'] = prog['default_status_fn']

    reset_statusbar = statusbar_def_reset(prog = prog)

    stddraw = WindowDrawState(stdscr)
    stdcurs = Cursor((0, 0))
    children = []

    sudoku_grid = curses.newpad(100, 100)
    sudoku_view = PadView(sudoku_grid, (0, 0), (2, 0), SMALL_GRID_SIZE)
    sudoku_draw = WindowDrawState(sudoku_grid)
    sudoku_draw.on_draw = sudoku_def_draw(
            pv = sudoku_view,
            prog = prog,
            reset_statusbar = reset_statusbar,
            cursor = stdcurs
            )
    children.append((sudoku_draw, sudoku_view))

    titlebar_win = curses.newwin(1, curses.COLS, 0, 0)
    titlebar = WindowDrawState(titlebar_win)
    titlebar.on_draw = titlebar_def_draw()
    children.append((titlebar,))

    statusbar_win = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    statusbar = WindowDrawState(statusbar_win)
    statusbar.on_draw = statusbar_def_draw(prog = prog)
    children.append((statusbar,))

    stddraw.on_draw = stddraw_def_draw(children = children, cursor = stdcurs)

    windraw_refresh(stddraw)

    while True:
        kbytes = getkbytes_blocking(stdscr)
        key = key_from_bytes(kbytes)
        if key is None: continue

        if kbytes[0] == curses.KEY_RESIZE:
            windraw_refresh(stddraw)
            continue
        if key == askey("q"):
            break
        if key == askey("C-C"):
            break
        if key == askey("C-L"):
            stdscr.clear()
            reset_statusbar()
            windraw_refresh(stddraw)
            continue
        if key == askey("+") or key == askey("="):
            puzzle.use_big_grid = True
            windraw_refresh(stddraw)
            continue
        if key == askey("-"):
            puzzle.use_big_grid = False
            windraw_refresh(stddraw)
            continue
        if key == askey("h") or key == askey("a") or kbytes[0] == curses.KEY_LEFT:
            if sudoku_move_rel_cursor(puzzle, x = -1): windraw_refresh(stddraw)
            continue
        if key == askey("l") or key == askey("d") or kbytes[0] == curses.KEY_RIGHT:
            if sudoku_move_rel_cursor(puzzle, x = 1): windraw_refresh(stddraw)
            continue
        if key == askey("j") or key == askey("s") or kbytes[0] == curses.KEY_DOWN:
            if sudoku_move_rel_cursor(puzzle, y = 1): windraw_refresh(stddraw)
            continue
        if key == askey("k") or key == askey("w") or kbytes[0] == curses.KEY_UP:
            if sudoku_move_rel_cursor(puzzle, y = -1): windraw_refresh(stddraw)
            continue
        if key == askey("H") or kbytes[0] == curses.KEY_HOME:
            sudoku_move_abs_cursor(puzzle, x = 0)
            windraw_refresh(stddraw)
            continue
        if key == askey("L") or kbytes[0] == curses.KEY_END:
            sudoku_move_abs_cursor(puzzle, x = 8)
            windraw_refresh(stddraw)
            continue
        if key == askey("J") or kbytes[0] == curses.KEY_NPAGE:
            sudoku_move_abs_cursor(puzzle, y = 8)
            windraw_refresh(stddraw)
            continue
        if key == askey("K") or kbytes[0] == curses.KEY_PPAGE:
            sudoku_move_abs_cursor(puzzle, y = 0)
            windraw_refresh(stddraw)
            continue
        if kbytes[0] == curses.KEY_BACKSPACE or kbytes[0] == curses.KEY_DC or key == askey("."):
            sudoku_del(puzzle)
            windraw_refresh(stddraw)
            continue
        if key == askey("n") or key == askey("0") or kbytes[0] == curses.KEY_IC:
            sudoku_toggle_note_mode(puzzle)
            windraw_refresh(stddraw)
            continue
        # TODO refactor
        if key == askey("1"):
            sudoku_ins(puzzle, 1)
            windraw_refresh(stddraw)
            continue
        if key == askey("2"):
            sudoku_ins(puzzle, 2)
            windraw_refresh(stddraw)
            continue
        if key == askey("3"):
            sudoku_ins(puzzle, 3)
            windraw_refresh(stddraw)
            continue
        if key == askey("4"):
            sudoku_ins(puzzle, 4)
            windraw_refresh(stddraw)
            continue
        if key == askey("5"):
            sudoku_ins(puzzle, 5)
            windraw_refresh(stddraw)
            continue
        if key == askey("6"):
            sudoku_ins(puzzle, 6)
            windraw_refresh(stddraw)
            continue
        if key == askey("7"):
            sudoku_ins(puzzle, 7)
            windraw_refresh(stddraw)
            continue
        if key == askey("8"):
            sudoku_ins(puzzle, 8)
            windraw_refresh(stddraw)
            continue
        if key == askey("9"):
            sudoku_ins(puzzle, 9)
            windraw_refresh(stddraw)
            continue

if __name__ == "__main__":
    curses.wrapper(main)

# vim: foldmethod=marker
