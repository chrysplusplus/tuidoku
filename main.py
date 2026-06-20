#!/usr/bin/env python3

"""
# TODO

- fix deprecated typings
- add reset command
- refine game controls
- implement grid scrolling
- implement puzzle generation
- implement undo
- implement line and box guides
"""

import curses
import collections

from dataclasses import dataclass, field, KW_ONLY
from functools import partial
from itertools import repeat
from typing import Callable

import tui

from util import clamp, set_cursor_shape
from tui import (
        L_ew, L_ns,
        L_es, L_sw, L_ne, L_nw,
        L_nes, L_nsw, L_esw, L_new, L_nesw,
        L_EW, L_NS,
        L_Es, L_eS, L_ES,
        L_Sw, L_Sw, L_SW,
        L_nE, L_Ne, L_NE,
        L_nW, L_Nw, L_NW,
        L_nEs, L_NeS, L_NES,
        L_nsW, L_NSw, L_NSW,
        L_EsW, L_eSw, L_ESW,
        L_nEW, L_New, L_NEW,
        L_nEsW, L_NeSw, L_NESW,
        C_es, C_sw, C_nw, C_ne)

debug_show: bool = False
debug_vals: dict = {}

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

@dataclass(slots = True)
class GridCell:
    num: int | None
    notes: tuple[int,...] = tuple()
    provided: bool = False

GAMEMODE_NONE   = 0
GAMEMODE_NORMAL = 1
GAMEMODE_NOTE   = 2
SUDOKU_MAX_MODE    = 2

@dataclass(slots = True)
class SudokuGrid:
    grid: list[GridCell]
    cursor: tuple[int, int] = (0, 0)
    mode: int = GAMEMODE_NORMAL

@dataclass(slots = True)
class OverlayItem:
    text: str
    callback: Callable[[], None]

@dataclass(slots = True)
class Overlay:
    message: str
    items: list[OverlayItem] = field(default_factory = list)
    _: KW_ONLY
    selection: int = -1

def init_curses(stdscr: curses.window):# {{{
    curses.raw()
    curses.use_default_colors()

    # init colors
    assert curses.COLOR_PAIRS > 3
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)

    global ATTR_PROV, ATTR_NOTE_CURS
    ATTR_PROV = curses.color_pair(1)
    ATTR_NOTE_CURS = curses.color_pair(2)
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
LARGE_GRID_CELL_SIZE = (3, 7)
SMALL_GRID = grid_lines(1, 3)
SMALL_GRID_SIZE = (len(SMALL_GRID), len(SMALL_GRID[0]))
SMALL_GRID_CELL_SIZE = (1, 1)

SUDOKU_GRID_MARGIN = 5
# TODO refactor error display
def is_small_screen(appdata: dict, reset_fn: Callable[[], None]) -> bool:# {{{
    draw_errmsg = "Screen too small to display grid"
    if SMALL_GRID_SIZE[0] > curses.LINES - SUDOKU_GRID_MARGIN:
        appdata["status"] = lambda: draw_errmsg
        appdata["sudoku_draw_last_err"] = True
        return True

    if appdata.get("sudoku_draw_last_err", False): # reset if resized screen is no longer too small
        reset_fn()
        appdata["sudoku_draw_last_err"] = False

    return False
# }}}

ATTR_NORMAL = curses.A_NORMAL
ATTR_UNDER = curses.A_UNDERLINE
ATTR_PROV: int      # initialised by init_curses
ATTR_NOTE_CURS: int # initialised by init_curses

def big_cell_attr(y: int, x: int, cell: GridCell, sudoku: SudokuGrid) -> int: # {{{
    at_cursor = (y, x) == sudoku.cursor
    note_mode = sudoku.mode == GAMEMODE_NOTE

    if cell.provided and at_cursor:
        return ATTR_PROV | curses.A_REVERSE
    elif cell.provided:
        return ATTR_PROV
    elif note_mode and at_cursor:
        return ATTR_NOTE_CURS | curses.A_REVERSE
    elif at_cursor:
        return ATTR_NORMAL | curses.A_REVERSE
    else:
        return ATTR_NORMAL
# }}}

def scale_big_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    return (6 * y + 2, 10 * x + 3)
# }}}

def draw_padded_cell(win: curses.window, y: int, x: int, lines: list[str], attr: int):# {{{
    dy = len(lines)
    assert dy != 0
    dx = len(lines[0])
    assert y != 0 and x != 0
    maxy, maxx = win.getmaxyx()
    assert y + dy != maxy and x + dx != maxx
    padline = " " * (dx + 2)
    win.addstr(y - 1, x - 1, padline, attr)
    for i, line in enumerate(lines):
        win.addstr(y + i, x - 1, " " + line + " ", attr)
    win.addstr(y + dy, x - 1, padline, attr)
# }}}

def resize_gridviews(bigpv: tui.PadView, smallpv: tui.PadView):# {{{
    bigh, bigw_ = LARGE_GRID_SIZE
    smallh, smallw = SMALL_GRID_SIZE
    bigh = clamp(bigh, curses.LINES - 5)
    bigw = clamp(bigw_ + smallw + 1, curses.COLS - 3)
    sy = 2
    bigsx = (curses.COLS - bigw) // 2
    smallsx = bigsx + bigw_ + 1
    bigpv.desired_screen_start = (sy, bigsx)
    bigpv.desired_view_size = (bigh, bigw)
    smallpv.desired_screen_start = (sy, smallsx)
    smallpv.desired_view_size = (smallh, smallw)
# }}}

def draw_big_grid(pv: tui.PadView, puzzle: SudokuGrid):# {{{
    win = pv.pad
    CELL_H, CELL_W = LARGE_GRID_CELL_SIZE
    tui.win_addlines(win, LARGE_GRID)

    cy, cx = puzzle.cursor

    for i, cell in enumerate(puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_big_grid_coords((y, x))
        attr = big_cell_attr(y, x, cell, puzzle)

        if cell.num is not None:
            digit = cell.num
            digit_lines = font_l[digit]
            draw_padded_cell(win, cur_y, cur_x, digit_lines, attr)
            continue

        if cell.notes is not None:
            digits = cell.notes
            digit_lines_parts = [["", "", ""], ["", "", ""], ["", "", ""]]
            for num in range(1, 10):
                line, col = divmod(num - 1, 3)
                digit_lines_parts[line][col] = str(num) if num in digits else " "
            digit_lines = [" ".join(line) for line in digit_lines_parts]
            draw_padded_cell(win, cur_y, cur_x, digit_lines, attr)
            continue

        else:
            lines = [" " * CELL_W for _ in range(CELL_H)]
            draw_padded_cell(win, cur_y, cur_x, lines, attr)
# }}}

def small_cell_attr(y: int, x: int, cell: GridCell, sudoku: SudokuGrid) -> int: # {{{
    at_cursor = (y, x) == sudoku.cursor
    note_mode = sudoku.mode == GAMEMODE_NOTE
    has_notes = len(cell.notes) != 0

    if cell.provided:
        return ATTR_PROV
    elif note_mode and at_cursor:
        return ATTR_NOTE_CURS
    elif has_notes:
        return ATTR_NOTE_CURS
    else:
        return ATTR_NORMAL
# }}}

def scale_small_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    return (2 * y + 1, 4 * x + 2)
# }}}

def draw_small_grid(pv: tui.PadView, puzzle: SudokuGrid):# {{{
    win = pv.pad
    tui.win_addlines(win, SMALL_GRID, x = 1)
    for i, cell in enumerate(puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_small_grid_coords((y, x))
        attr = small_cell_attr(y, x, cell, puzzle)
        digit = ' '
        if cell.num is not None:
            digit = str(cell.num)
        elif len(cell.notes) != 0:
            digit = 'n'
        win.addstr(cur_y, cur_x + 1, digit, attr)
# }}}

def big_sudoku_draw(appdata: dict, pv: tui.PadView, reset_statusbar: Callable[[], None], win: curses.window) -> bool:# {{{
    assert id(win) == id(pv.pad)
    win.erase()
    if is_small_screen(appdata, reset_statusbar):
        return True

    puzzle = appdata.get("puzzle", None)
    assert puzzle is not None
    draw_big_grid(pv, puzzle)
    return True
# }}}

def small_sudoku_draw(appdata: dict, pv: tui.PadView, cursor: tui.Cursor, reset_statusbar: Callable[[], None], win: curses.window):# {{{
    assert id(win) == id(pv.pad)
    win.erase()
    # TODO refactor to prevent this being called twice
    if is_small_screen(appdata, reset_statusbar):
        return True

    puzzle = appdata.get("puzzle", None)
    assert puzzle is not None

    draw_small_grid(pv, puzzle)
    cy, cx = scale_small_grid_coords(puzzle.cursor)
    _, _, sy, sx, _, _ = tui.padview_clamp(pv)
    cursor.cursor = (cy + sy, cx + sx + 1)
    return True
# }}}

def padview_bounding_box(pv: tui.PadView) -> tuple[int, int, int, int]:# {{{
    py, px, sy, sx, msy, msx = tui.padview_clamp(pv)
    mpy = py + msy - sy
    mpx = px + msx - sx
    return py, px, mpy, mpx
# }}}

def big_gridview_bounding_box(bigpv: tui.PadView, smallpv: tui.PadView) -> tuple[int, int, int, int]:# {{{
    by, bx, mby, mbx = padview_bounding_box(bigpv)
    _, _, _, sx, _, _ = tui.padview_clamp(smallpv)
    mbx = min(mbx, sx + bx - 1)
    return by, bx, mby, mbx
# }}}

def big_sudoku_grid_cell_bounding_box(coords: tuple[int, int]) -> tuple[int, int, int, int]:# {{{
    cy, cx = scale_big_grid_coords(coords)
    ch, cw = LARGE_GRID_CELL_SIZE
    cy = cy - 2
    cx = cx - 3
    mcy = cy + ch + 3
    mcx = cx + cw + 4
    return cy, cx, mcy, mcx
# }}}

def nudge_coords_into_view(bigpv: tui.PadView, smallpv: tui.PadView, coords: tuple[int, int]):# {{{
    py, px, mpy, mpx = big_gridview_bounding_box(bigpv, smallpv)
    cy, cx, mcy, mcx = big_sudoku_grid_cell_bounding_box(coords)

    nudgey = 0
    if cy < py:
        nudgey = cy - py
    elif mcy > mpy:
        nudgey = mcy - mpy

    nudgex = 0
    if cx < px:
        nudgex = cx - px
    elif mcx > mpx:
        nudgex = mcx - mpx

    bigpv.pad_start = (py + nudgey, px + nudgex)
# }}}

def sudoku_move_abs_cursor(bigpv: tui.PadView, smallpv: tui.PadView, sudoku: SudokuGrid, *, y: int | None = None, x: int | None = None):# {{{
    oldy, oldx = sudoku.cursor
    newy = y if y is not None else oldy
    newx = x if x is not None else oldx
    sudoku.cursor = (newy, newx)
    nudge_coords_into_view(bigpv, smallpv, (newy, newx))
# }}}

def sudoku_move_rel_cursor(bigpv: tui.PadView, smallpv: tui.PadView, sudoku: SudokuGrid, *, y: int = 0, x: int = 0) -> bool: # {{{
    '''Returns True if cursor changed, otherwise False'''
    oldy, oldx = sudoku.cursor
    newy = (oldy + y) % 9
    newx = (oldx + x) % 9
    sudoku.cursor = (newy, newx)
    nudge_coords_into_view(bigpv, smallpv, (newy, newx))
    return (oldy, oldx) != (newy, newx)
# }}}

MODE_STRINGS = [ "", "-- NORMAL --", "-- NOTE --" ]# {{{
MAX_MODE_STRING = len(MODE_STRINGS)
# }}}

def sudoku_mode(sudoku: SudokuGrid) -> str:# {{{
    return MODE_STRINGS[clamp(sudoku.mode, MAX_MODE_STRING, 0)]
# }}}

# TODO refactor as Actions
def sudoku_ins(sudoku: SudokuGrid, digit: int):# {{{
    if digit < 1 or digit > 9: return
    cy, cx = sudoku.cursor
    index = 9 * cy + cx

    if sudoku.grid[index].provided: return

    old_num = sudoku.grid[index].num
    old_notes = sudoku.grid[index].notes
    if sudoku.mode == GAMEMODE_NORMAL and digit == old_num:
        sudoku.grid[index].num = None
    elif sudoku.mode == GAMEMODE_NORMAL:
        sudoku.grid[index].num = digit
    elif sudoku.mode == GAMEMODE_NOTE and digit in old_notes:
        sudoku.grid[index].notes = tuple(d for d in old_notes if d != digit)
    elif sudoku.mode == GAMEMODE_NOTE:
        sudoku.grid[index].notes = (*old_notes, digit)
# }}}

# TODO refactor as Actions
def sudoku_del(sudoku: SudokuGrid):# {{{
    cy, cx = sudoku.cursor
    i = 9 * cy + cx
    if sudoku.grid[i].provided: return
    if sudoku.mode == GAMEMODE_NORMAL:
        sudoku.grid[i].num = None
    elif sudoku.mode == GAMEMODE_NOTE and sudoku.grid[i].num is not None:
        sudoku.grid[i].num = None
    elif sudoku.mode == GAMEMODE_NOTE:
        sudoku.grid[i].notes = tuple()
# }}}

def sudoku_toggle_note_mode(sudoku: SudokuGrid):# {{{
    sudoku.mode = GAMEMODE_NORMAL if sudoku.mode == GAMEMODE_NOTE else GAMEMODE_NOTE
# }}}

def debug_screen_draw(pv: tui.PadView, win: curses.window) -> bool:# {{{
    global debug_show, debug_vals
    assert id(pv.pad) == id(win)
    win.erase()
    if debug_show:
        maxy, maxx = win.getmaxyx()
        maxx = min(maxx, curses.COLS - 1)
        assert maxy > 2
        win.addstr(0, 0, "Debug", ATTR_NORMAL)
        y = 1
        w = 6
        for key, value in debug_vals.items():
            line = f"{key}: {value}"[:maxx + 0]
            w = max(w, len(line))
            win.addstr(y, 0, line, ATTR_NORMAL)
            y += 1
            if y == maxy:
                break

        pv.desired_view_size = (y , w)

    else:
        pv.desired_view_size = (0, 0)

    return True
# }}}

def titlebar_draw(win: curses.window) -> bool:# {{{
    win.erase()
    _, maxx = win.getmaxyx()
    text = "SUDOKU"[:maxx + 1]
    win.addstr(0, (maxx - len(text)) // 2, text)
    return True
# }}}

def statusbar_draw(appdata: dict, win: curses.window) -> bool:# {{{
    status = appdata.get("status", "")
    win.mvwin(curses.LINES - 1, 0)
    _, maxx = win.getmaxyx()
    win.erase()
    txt = status() if callable(status) else str(status)
    win.addstr(txt[:maxx + 1])
    return True
# }}}

def statusbar_reset(appdata: dict):# {{{
    appdata['status'] = appdata.get("default_status", "")
# }}}

def move_cursor(appdata: dict, y: int = 0, x: int = 0) -> bool:# {{{
    if (cursor_fn := appdata.get("cursor_fn", None)) is None:
        return False
    return cursor_fn(y = y, x = x)
# }}}

def window_mappings(stdwin: tui.MainWindow, big_sudoku_view: tui.PadView, small_sudoku_view: tui.PadView, puzzle: SudokuGrid, reset_statusbar: Callable[[], None]):# {{{
    stdscr = stdwin.stdscr

    def on_resize():
        curses.update_lines_cols()
        resize_gridviews(big_sudoku_view, small_sudoku_view)
        big_sudoku_view.pad_start = (0, 0)
        nudge_coords_into_view(big_sudoku_view, small_sudoku_view, puzzle.cursor)
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("KEY_RESIZE"), on_resize)

    def on_reset():
        stdscr.clear()
        reset_statusbar()
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("C-L"), on_reset)

    def on_debug_toggle():
        global debug_show
        debug_show = not debug_show
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("g"), on_debug_toggle)
# }}}

def cursor_mappings(stdwin: tui.MainWindow, appdata: dict):# {{{
    def on_move_rel(y = 0, x = 0):
        if move_cursor(appdata, y = y, x = x):
            stdwin.refresh()

    mv_left = partial(on_move_rel, x = -1)
    stdwin.add_mapping(tui.askey("h"), mv_left)
    stdwin.add_mapping(tui.askey("a"), mv_left)
    stdwin.add_mapping(tui.askey("KEY_LEFT"), mv_left)

    mv_right = partial(on_move_rel, x = 1)
    stdwin.add_mapping(tui.askey("l"), mv_right)
    stdwin.add_mapping(tui.askey("d"), mv_right)
    stdwin.add_mapping(tui.askey("KEY_RIGHT"), mv_right)

    mv_down = partial(on_move_rel, y = 1)
    stdwin.add_mapping(tui.askey("j"), mv_down)
    stdwin.add_mapping(tui.askey("s"), mv_down)
    stdwin.add_mapping(tui.askey("KEY_DOWN"), mv_down)

    mv_up = partial(on_move_rel, y = -1)
    stdwin.add_mapping(tui.askey("k"), mv_up)
    stdwin.add_mapping(tui.askey("w"), mv_up)
    stdwin.add_mapping(tui.askey("KEY_UP"), mv_up)

# }}}

def sudoku_mappings(stdwin: tui.MainWindow, big_sudoku_view: tui.PadView, small_sudoku_view: tui.PadView, puzzle: SudokuGrid, on_overlay_confirm: Callable[..., Overlay]):# {{{
    def on_move_abs(y: int | None = None, x: int | None = None):
        sudoku_move_abs_cursor(big_sudoku_view, small_sudoku_view, puzzle, y = y, x = x)
        stdwin.refresh()

    mv_first = partial(on_move_abs, x = 0)
    stdwin.add_mapping(tui.askey("H"), mv_first)
    stdwin.add_mapping(tui.askey("KEY_HOME"), mv_first)

    mv_last = partial(on_move_abs, x = 8)
    stdwin.add_mapping(tui.askey("L"), mv_last)
    stdwin.add_mapping(tui.askey("KEY_END"), mv_last)

    mv_bottom = partial(on_move_abs, y = 8)
    stdwin.add_mapping(tui.askey("J"), mv_bottom)
    stdwin.add_mapping(tui.askey("KEY_NPAGE"), mv_bottom)

    mv_top = partial(on_move_abs, y = 0)
    stdwin.add_mapping(tui.askey("K"), mv_top)
    stdwin.add_mapping(tui.askey("KEY_PPAGE"), mv_top)

    def on_delete():
        sudoku_del(puzzle)
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("KEY_BACKSPACE"), on_delete)
    stdwin.add_mapping(tui.askey("KEY_DC"), on_delete)
    stdwin.add_mapping(tui.askey("."), on_delete)

    def on_toggle_notes():
        sudoku_toggle_note_mode(puzzle)
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("n"), on_toggle_notes)
    stdwin.add_mapping(tui.askey("0"), on_toggle_notes)
    stdwin.add_mapping(tui.askey("KEY_IC"), on_toggle_notes)

    def on_digit(digit: int):
        sudoku_ins(puzzle, digit)
        stdwin.refresh()

    for digit in range(1, 10):
        stdwin.add_mapping(tui.askey(str(digit)), partial(on_digit, digit))

    def on_quit():
        puzzle.mode = 0 # TODO figure out how to restore this
        on_overlay_confirm("Are you sure you want to quit?", ("&Yes", stdwin.quit), ("&No",), selection = 1)

    stdwin.add_mapping(tui.askey("q"), on_quit)
# }}}

# }}}

def confirm_draw(pv: tui.PadView, appdata: dict, win: curses.window):# {{{
    overlay = appdata.get("overlay", None)
    assert overlay is not None
    win.erase()
    padding = 1
    maxy, maxx = win.getmaxyx()
    maxx = min(maxx, curses.COLS - (padding * 2) - 1)
    msg = (" " * padding) + overlay.message[:maxx] + (" " * padding)
    h = 3 + (padding * 2)
    w = len(msg) + 2

    win.addstr(padding, 1, msg, ATTR_NORMAL)
    tui.draw_box(win, 0, 0, h, w, ATTR_NORMAL)

    GAP_SENTINEL = object()
    cursor_pre = ("> ", ATTR_NORMAL)
    cursor_post = (" <", ATTR_NORMAL)
    nocurs_pre = ("  ", ATTR_NORMAL)
    nocurs_post = ("  ", ATTR_NORMAL)

    rendered = []
    rendered_width = 0
    for index, item in enumerate(overlay.items):
        text = item.text
        if overlay.selection == index and text[0] == '&':
            rendered.append(GAP_SENTINEL)
            rendered.append(cursor_pre)
            rendered.append((text[1], ATTR_UNDER))
            rendered.append((text[2:], ATTR_NORMAL))
            rendered.append(cursor_post)
            rendered_width += len(text) + 3

        elif overlay.selection == index:
            rendered.append(GAP_SENTINEL)
            rendered.append(cursor_pre)
            rendered.append((text, ATTR_NORMAL))
            rendered.append(cursor_post)
            rendered_width += len(text) + 4

        elif text[0] == '&':
            rendered.append(GAP_SENTINEL)
            rendered.append(nocurs_pre)
            rendered.append((text[1], ATTR_UNDER))
            rendered.append((text[2:], ATTR_NORMAL))
            rendered.append(nocurs_post)
            rendered_width += len(text) + 3

        else:
            rendered.append(GAP_SENTINEL)
            rendered.append(GAP_SENTINEL)
            rendered.append(nocurs_pre)
            rendered.append((text, ATTR_NORMAL))
            rendered.append(nocurs_post)
            rendered_width += len(text) + 4

    gaplen = (len(msg) - rendered_width) // (len(overlay.items) + 1)
    gap = " " * gaplen
    y = padding + 2
    x = 1
    for item in rendered:
        if item is GAP_SENTINEL:
            win.addstr(y, x, gap, ATTR_NORMAL)
            x += gaplen
        else:
            text, attr = item
            win.addstr(y, x, text, attr)
            x += len(text)

    pv.desired_view_size = (h, w)
    pv.desired_screen_start = ((curses.LINES - h) // 2, (curses.COLS - w) // 2)
    return True
# }}}

def confirm_move_cursor(appdata: dict, y: int = 0, x: int = 0) -> bool:# {{{
    overlay = appdata.get("overlay", None)
    assert overlay is not None
    if y > 0 or x > 0:
        overlay.selection = (overlay.selection + 1) % len(overlay.items)
    if y < 0 or x < 0:
        overlay.selection = (overlay.selection - 1) % len(overlay.items)
    return True
# }}}

def confirm_select_cursor(appdata: dict):# {{{
    overlay = appdata.get("overlay", None)
    assert overlay is not None
    if overlay.selection < 0 or overlay.selection >= len(overlay.items):
        return
    return overlay.items[overlay.selection].callback()
# }}}

def overlay_accel_keys(overlay: Overlay) -> list[tuple[str, Callable[[], None]]]:# {{{
    accel_keys = []
    for item in overlay.items:
        if item.text[0] == '&':
            accel_keys.append((item.text[1].lower(), item.callback))
    return accel_keys
# }}}

# TODO make not hardcoded?
def confirm_restore(appdata: dict, restore_cursor_fn: Callable[[int, int], bool]):# {{{
    appdata["cursor_fn"] = restore_cursor_fn
# }}}

def overlay_confirm(stdwin: tui.MainWindow, overlay_windraw: tui.WindowDrawState, overlay_view: tui.PadView, big_sudoku_view: tui.PadView, small_sudoku_view: tui.PadView, puzzle: SudokuGrid, reset_statusbar: Callable[[], None], appdata: dict, msg: str, *items, selection: int = -1) -> Overlay:# {{{
    '''items are tuples of (text, callback) or (text,), the latter of which
    will assigned the callback to quit the overlay and restore the display'''

    assert overlay_windraw.on_draw is None
    restore_cursor_fn = appdata['cursor_fn']
    dp = tui.DisplayRestore(stdwin, overlay_windraw, overlay_view, partial(confirm_restore, appdata, restore_cursor_fn))
    stdwin.keymap = collections.OrderedDict()
    appdata["cursor_fn"] = partial(confirm_move_cursor, appdata)

    on_confirm_restore = partial(tui.display_restore, dp)
    overlay = Overlay(msg, selection = selection)
    for item in items:
        if len(item) == 1:
            overlay.items.append(OverlayItem(item[0], on_confirm_restore))
        else:
            text, callback = item
            overlay.items.append(OverlayItem(text, callback))

    appdata["overlay"] = overlay
    overlay_windraw.on_draw = partial(confirm_draw, overlay_view, appdata)

    # TODO refactor into mapping layers
    window_mappings(stdwin, big_sudoku_view, small_sudoku_view, puzzle, reset_statusbar)
    cursor_mappings(stdwin, appdata)

    on_select = partial(confirm_select_cursor, appdata)
    stdwin.add_mapping(tui.askey("KEY_ENTER"), on_select)
    stdwin.add_mapping(tui.askey("C-H"), on_select)
    stdwin.add_mapping(tui.askey("C-J"), on_select)

    accel_keys_blacklist = 'hjkl'
    for key, callback in overlay_accel_keys(appdata['overlay']):
        stdwin.add_mapping(tui.askey(key), callback)

    stdwin.refresh()
# }}}

EXAMPLE_PUZZLE = "6...5...7 .9.1..3.. 7..6..94. 8..34.1.. ...5.1... ..5.87..9 .68..2..4 ..1..6.9. 3...9...1"
PUZZLE_SOLUTION = ""

def main(stdwin: tui.MainWindow):
    puzzle_input = EXAMPLE_PUZZLE
    puzzle: SudokuGrid = grid_from_str(puzzle_input, provided = True)
    stddraw = stdwin.stddraw
    stdscr = stdwin.stdscr

    stdwin.stdcurs.cursor = (-1, -1)

    appdata = {
            "default_status": partial(sudoku_mode, puzzle),
            "sudoku_draw_last_err": False,
            "puzzle_input": puzzle_input,
            "puzzle": puzzle
            }

    reset_statusbar = partial(statusbar_reset, appdata)
    reset_statusbar()

    big_sudoku_win = curses.newpad(100, 100)
    big_sudoku_view = tui.PadView(big_sudoku_win, (0, 0), (2, 0), (0, 0))
    big_sudoku = tui.WindowDrawState(big_sudoku_win)
    big_sudoku.on_draw = partial(big_sudoku_draw, appdata, big_sudoku_view, reset_statusbar)
    stdwin.add_child(big_sudoku, big_sudoku_view)

    small_sudoku_win = curses.newpad(50, 50)
    small_sudoku_view = tui.PadView(small_sudoku_win, (0, 0), (2, 0), (0, 0))
    small_sudoku = tui.WindowDrawState(small_sudoku_win)
    small_sudoku.on_draw = partial(small_sudoku_draw, appdata, small_sudoku_view, stdwin.stdcurs, reset_statusbar)
    stdwin.add_child(small_sudoku, small_sudoku_view)

    resize_gridviews(big_sudoku_view, small_sudoku_view)

    overlay_win = curses.newpad(100, 100)
    overlay_view = tui.PadView(overlay_win, (0, 0), (0, 0), (0, 0))
    overlay = tui.WindowDrawState(overlay_win)
    stdwin.add_child(overlay, overlay_view)

    titlebar_win = curses.newwin(1, curses.COLS, 0, 0)
    titlebar = tui.WindowDrawState(titlebar_win)
    titlebar.on_draw = titlebar_draw
    stdwin.add_child(titlebar)

    debug_screen_win = curses.newpad(100, 100)
    debug_screen_view = tui.PadView(debug_screen_win, (0, 0), (0, 0), (0, 0))
    debug_screen = tui.WindowDrawState(debug_screen_win)
    debug_screen.on_draw = partial(debug_screen_draw, debug_screen_view)
    stdwin.add_child(debug_screen, debug_screen_view)

    statusbar_win = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    statusbar = tui.WindowDrawState(statusbar_win)
    statusbar.on_draw = partial(statusbar_draw, appdata)
    stdwin.add_child(statusbar)

    tui.windraw_refresh(stddraw)

    on_move_sudoku_cursor = partial(sudoku_move_rel_cursor, big_sudoku_view, small_sudoku_view, puzzle)
    appdata["cursor_fn"] = on_move_sudoku_cursor

    #(msg: str, * items, selection: int = -1) -> Overlay:
    on_overlay_confirm = partial(overlay_confirm, stdwin, overlay, overlay_view, big_sudoku_view, small_sudoku_view, puzzle, reset_statusbar, appdata)

    window_mappings(stdwin, big_sudoku_view, small_sudoku_view, puzzle, reset_statusbar)
    cursor_mappings(stdwin, appdata)
    sudoku_mappings(stdwin, big_sudoku_view, small_sudoku_view, puzzle, on_overlay_confirm)

    #stdwin.add_mapping(tui.askey("q"), stdwin.quit)
    stdwin.add_mapping(tui.askey("C-C"), stdwin.quit)

    stdwin.mainloop()

if __name__ == "__main__":
    set_cursor_shape()
    curses.wrapper(tui.start_curses, init_curses, main)

# vim: foldmethod=marker
