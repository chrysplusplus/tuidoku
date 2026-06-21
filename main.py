#!/usr/bin/env python3

"""
# TODO

- test SudokuApp coverage
- add reset command
- refine game controls
- implement grid scrolling
- implement puzzle generation
- implement undo
- implement line and box guides

## Notes from Playtesting

- controls information underneath small grid

"""

import curses
import collections

from collections.abc import Callable
from dataclasses import dataclass, field, KW_ONLY
from functools import partial
from itertools import repeat

import tui

from util import clamp, pad_text, Invoke
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
    info: list[str] = field(default_factory = list)

class SudokuApp:
    def __init__(self, stdwin: tui.MainWindow, puzzle_input: str):# {{{
        self.stdwin = stdwin
        self.puzzle_input = puzzle_input
        self.puzzle: SudokuGrid = grid_from_str(puzzle_input, provided = True)
        self.appdata = {
                "default_status": partial(sudoku_mode, self.puzzle),
                "sudoku_draw_last_err": False,
                "puzzle_input": self.puzzle_input,
                "puzzle": self.puzzle}
        self.reset_statusbar = partial(statusbar_reset, self.appdata)

        self.init_big_sudoku()
        self.init_small_sudoku()
        self.init_overlay()
        self.init_titlebar()
        self.init_debug_screen()
        self.init_statusbar()

        self.on_overlay_confirm = partial(overlay_confirm, self)
# }}}
    def init_big_sudoku(self):# {{{
        self.big_sudoku_win = curses.newpad(100, 100)
        self.big_sudoku_view = tui.PadView(self.big_sudoku_win, (0, 0), (2, 0), (0, 0))
        self.big_sudoku = tui.WindowDrawState(self.big_sudoku_win)
        self.big_sudoku.on_draw = partial(big_sudoku_draw, self)
        self.stdwin.add_child(self.big_sudoku, self.big_sudoku_view)
# }}}
    def init_small_sudoku(self):# {{{
        self.small_sudoku_win = curses.newpad(50, 50)
        self.small_sudoku_view = tui.PadView(self.small_sudoku_win, (0, 0), (2, 0), (0, 0))
        self.small_sudoku = tui.WindowDrawState(self.small_sudoku_win)
        self.small_sudoku.on_draw = partial(small_sudoku_draw, self)
        self.stdwin.add_child(self.small_sudoku, self.small_sudoku_view)
# }}}
    def init_overlay(self):# {{{
        self.overlay_win = curses.newpad(100, 100)
        self.overlay_view = tui.PadView(self.overlay_win, (0, 0), (0, 0), (0, 0))
        self.overlay = tui.WindowDrawState(self.overlay_win)
        self.stdwin.add_child(self.overlay, self.overlay_view)
# }}}
    def init_titlebar(self):# {{{
        self.titlebar_win = curses.newwin(1, curses.COLS, 0, 0)
        self.titlebar = tui.WindowDrawState(self.titlebar_win)
        self.titlebar.on_draw = titlebar_draw
        self.stdwin.add_child(self.titlebar)
# }}}
    def init_debug_screen(self):# {{{
        self.debug_screen_win = curses.newpad(100, 100)
        self.debug_screen_view = tui.PadView(self.debug_screen_win, (0, 0), (0, 0), (0, 0))
        self.debug_screen = tui.WindowDrawState(self.debug_screen_win)
        self.debug_screen.on_draw = partial(debug_screen_draw, self)
        self.stdwin.add_child(self.debug_screen, self.debug_screen_view)

        self.debug_show = False
        self.debug_vals = {}
# }}}
    def init_statusbar(self):# {{{
        self.statusbar_win = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
        self.statusbar = tui.WindowDrawState(self.statusbar_win)
        self.statusbar.on_draw = partial(statusbar_draw, self)
        self.stdwin.add_child(self.statusbar)
# }}}

def init_curses(stdscr: curses.window):# {{{
    curses.raw()
    curses.use_default_colors()

    # init colors
    assert curses.COLOR_PAIRS > 3
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)

    global ATTR_PROV, ATTR_NOTE
    ATTR_PROV = curses.color_pair(1)
    ATTR_NOTE = curses.color_pair(2)
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
    line_format = "{outer_left}" + "{box_border}".join(repeat("{cell_border}".join(repeat("{cell_inner}" * cell_width, 3)), 3)) + "{outer_right}"

    line_outer_top = line_format.format(outer_left = L_ES, outer_right = L_SW, box_border = L_ESW, cell_border = L_EsW, cell_inner = L_EW)
    line_outer_bottom = line_format.format(outer_left = L_NE, outer_right = L_NW, box_border = L_NEW, cell_border = L_nEW, cell_inner = L_EW)
    line_box_border = line_format.format(outer_left = L_NES, outer_right = L_NSW, box_border = L_NESW, cell_border = L_nEsW, cell_inner = L_EW)
    line_cell_border = line_format.format(outer_left = L_NeS, outer_right = L_NSw, box_border = L_NeSw, cell_border = L_nesw, cell_inner = L_ew)
    line_cell_inner = line_format.format(outer_left = L_NS, outer_right = L_NS, box_border = L_NS, cell_border = L_ns, cell_inner = " ")

    cell_lines = list(repeat(line_cell_inner, cell_height))
    box_lines = cell_lines.copy()
    for lines in repeat(cell_lines, 3 - 1): # 3 cell rows (1 already accounted for)
        box_lines.append(line_cell_border)
        box_lines += lines

    grid = [line_outer_top] + box_lines
    for lines in repeat(box_lines, 3 - 1): # 3 box rows (1 already accounted for)
        grid.append(line_box_border)
        grid += lines

    grid.append(line_outer_bottom)
    return grid
# }}}

LARGE_GRID = grid_lines(5, 9)
LARGE_GRID_SIZE = (len(LARGE_GRID), len(LARGE_GRID[0]))
LARGE_GRID_CELL_SIZE = (3, 7)
SMALL_GRID = grid_lines(1, 3)
SMALL_GRID_SIZE = (len(SMALL_GRID), len(SMALL_GRID[0]))
SMALL_GRID_CELL_SIZE = (1, 1)

SUDOKU_GRID_MARGIN = 5
def is_small_screen() -> bool:# {{{
    return SMALL_GRID_SIZE[0] > curses.LINES - SUDOKU_GRID_MARGIN
# }}}

ATTR_NORMAL = curses.A_NORMAL
ATTR_UNDER = curses.A_UNDERLINE
ATTR_PROV: int      # initialised by init_curses
ATTR_NOTE: int # initialised by init_curses

def big_cell_attr(y: int, x: int, cell: GridCell, sudoku: SudokuGrid) -> int:# {{{
    at_cursor = (y, x) == sudoku.cursor
    note_mode = sudoku.mode == GAMEMODE_NOTE

    if cell.provided and at_cursor:
        return ATTR_PROV | curses.A_REVERSE
    elif cell.provided:
        return ATTR_PROV
    elif note_mode and at_cursor:
        return ATTR_NOTE | curses.A_REVERSE
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

def resize_gridviews(app: SudokuApp):# {{{
    bigpv = app.big_sudoku_view
    smallpv = app.small_sudoku_view
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
    else:
        return ATTR_NORMAL
# }}}

def scale_small_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    if y < 0 or y > 8 or x < 0 or x > 8:
        return (-1, -1)
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
        win.addstr(cur_y, cur_x + 1, digit, attr)
# }}}

def big_sudoku_draw(app: SudokuApp, win: curses.window) -> bool:# {{{
    pv = app.big_sudoku_view
    assert id(win) == id(pv.pad)
    win.erase()
    if is_small_screen():
        app.appdata["small_screen"] = True
        app.appdata["status"] = "Screen too small to display grid"
        return True

    elif app.appdata.get("small_screen", False):
        # clear previous small screen report
        app.appdata["small_screen"] = False
        app.reset_statusbar()

    puzzle = app.appdata.get("puzzle", None)
    assert puzzle is not None
    draw_big_grid(pv, puzzle)
    return True
# }}}

def small_sudoku_draw(app: SudokuApp, win: curses.window):# {{{
    pv = app.small_sudoku_view
    assert id(win) == id(pv.pad)
    win.erase()
    if app.appdata.get("small_screen", False):
        return True

    puzzle = app.appdata.get("puzzle", None)
    assert puzzle is not None

    draw_small_grid(pv, puzzle)
    cy, cx = scale_small_grid_coords(puzzle.cursor)
    if cy > 0 and cx > 0:
        _, _, sy, sx, _, _ = tui.padview_clamp(pv)
        app.stdwin.stdcurs.cursor = (cy + sy, cx + sx + 1)
    return True
# }}}

def padview_bounding_box(pv: tui.PadView) -> tuple[int, int, int, int]:# {{{
    py, px, sy, sx, msy, msx = tui.padview_clamp(pv)
    mpy = py + msy - sy
    mpx = px + msx - sx
    return py, px, mpy, mpx
# }}}

def big_gridview_bounding_box(app: SudokuApp) -> tuple[int, int, int, int]:# {{{
    by, bx, mby, mbx = padview_bounding_box(app.big_sudoku_view)
    _, _, _, sx, _, _ = tui.padview_clamp(app.small_sudoku_view)
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

def nudge_coords_into_view(app, coords: tuple[int, int]):# {{{
    py, px, mpy, mpx = big_gridview_bounding_box(app)
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

    app.big_sudoku_view.pad_start = (py + nudgey, px + nudgex)
# }}}

def sudoku_move_abs_cursor(app:  SudokuApp, *, y: int | None = None, x: int | None = None):# {{{
    bigpv = app.big_sudoku_view
    smallpv = app.small_sudoku_view
    oldy, oldx = app.puzzle.cursor
    newy = y if y is not None else oldy
    newx = x if x is not None else oldx
    app.puzzle.cursor = (newy, newx)
    nudge_coords_into_view(app, (newy, newx))
# }}}

def sudoku_move_rel_cursor(app: SudokuApp, *, y: int = 0, x: int = 0) -> bool: # {{{
    '''Returns True if cursor changed, otherwise False'''
    bigpv = app.big_sudoku_view
    smallpv = app.small_sudoku_view
    oldy, oldx = app.puzzle.cursor
    newy = (oldy + y) % 9
    newx = (oldx + x) % 9
    app.puzzle.cursor = (newy, newx)
    nudge_coords_into_view(app, (newy, newx))
    return (oldy, oldx) != (newy, newx)
# }}}

MODE_STRINGS = [ "", "-- NORMAL --", "-- NOTE --" ]# {{{
MAX_MODE_STRING = len(MODE_STRINGS)
# }}}

def sudoku_mode(sudoku: SudokuGrid) -> str:# {{{
    return MODE_STRINGS[clamp(sudoku.mode, MAX_MODE_STRING, 0)]
# }}}

# TODO refactor as Actions
def sudoku_ins(app: SudokuApp, digit: int):# {{{
    sudoku = app.puzzle
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
def sudoku_del(app: SudokuApp):# {{{
    sudoku = app.puzzle
    cy, cx = sudoku.cursor
    i = 9 * cy + cx
    if sudoku.grid[i].provided: return
    if sudoku.grid[i].num is not None:
        sudoku.grid[i].num = None
    else:
        sudoku.grid[i].notes = tuple()
# }}}

def sudoku_toggle_note_mode(sudoku: SudokuGrid):# {{{
    sudoku.mode = GAMEMODE_NORMAL if sudoku.mode == GAMEMODE_NOTE else GAMEMODE_NOTE
# }}}

def debug_screen_draw(app: SudokuApp, win: curses.window) -> bool:# {{{
    pv = app.debug_screen_view
    assert id(pv.pad) == id(win)
    win.erase()
    if app.debug_show:
        maxy, maxx = win.getmaxyx()
        maxx = min(maxx, curses.COLS - 1)
        assert maxy > 2
        win.addstr(0, 0, "Debug", ATTR_NORMAL)
        y = 1
        w = 6
        for key, value in app.debug_vals.items():
            if callable(value):
                value = value()

            line = f"{key}: {value}"[:maxx]
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

def statusbar_draw(app: SudokuApp, win: curses.window) -> bool:# {{{
    status = app.appdata.get("status", "")
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

def map_window(app: SudokuApp):# {{{
    stdscr = app.stdwin.stdscr

    def on_resize():
        curses.update_lines_cols()
        resize_gridviews(app)
        app.big_sudoku_view.pad_start = (0, 0)
        nudge_coords_into_view(app, app.puzzle.cursor)
        app.stdwin.refresh()

    app.stdwin.add_mapping(tui.askey("KEY_RESIZE"), on_resize)

    def on_reset():
        stdscr.clear()
        app.reset_statusbar()
        app.stdwin.refresh()

    app.stdwin.add_mapping(tui.askey("C-L"), on_reset)

    def on_debug_toggle():
        app.debug_show = not app.debug_show
        app.stdwin.refresh()

    app.stdwin.add_mapping(tui.askey("g"), on_debug_toggle)

    # TODO implement safety catch for Ctrl-C
    app.stdwin.add_mapping(tui.askey("C-C"), app.stdwin.quit)
# }}}

def map_cursor(app: SudokuApp):# {{{
    def on_move_rel(y = 0, x = 0):
        if move_cursor(app.appdata, y = y, x = x):
            app.stdwin.refresh()

    mv_left = partial(on_move_rel, x = -1)
    app.stdwin.add_mapping(tui.askey("h"), mv_left)
    app.stdwin.add_mapping(tui.askey("a"), mv_left)
    app.stdwin.add_mapping(tui.askey("KEY_LEFT"), mv_left)

    mv_right = partial(on_move_rel, x = 1)
    app.stdwin.add_mapping(tui.askey("l"), mv_right)
    app.stdwin.add_mapping(tui.askey("d"), mv_right)
    app.stdwin.add_mapping(tui.askey("KEY_RIGHT"), mv_right)

    mv_down = partial(on_move_rel, y = 1)
    app.stdwin.add_mapping(tui.askey("j"), mv_down)
    app.stdwin.add_mapping(tui.askey("s"), mv_down)
    app.stdwin.add_mapping(tui.askey("KEY_DOWN"), mv_down)

    mv_up = partial(on_move_rel, y = -1)
    app.stdwin.add_mapping(tui.askey("k"), mv_up)
    app.stdwin.add_mapping(tui.askey("w"), mv_up)
    app.stdwin.add_mapping(tui.askey("KEY_UP"), mv_up)
# }}}

def map_base(app: SudokuApp):# {{{
    map_window(app)
    map_cursor(app)
# }}}

def sudoku_restore(app: SudokuApp, on_move_sudoku_cursor: Callable[[], None], restore_cursor: tuple[int, int], restore_mode: int):# {{{
    app.appdata["cursor_fn"] = on_move_sudoku_cursor
    app.puzzle.cursor = restore_cursor
    app.puzzle.mode = restore_mode
# }}}

def map_final_quit(stdwin: tui.MainWindow):# {{{
    stdwin.add_mapping(tui.askey("q"), stdwin.quit)
# }}}

def map_sudoku(app: SudokuApp):# {{{
    on_move_sudoku_cursor = partial(sudoku_move_rel_cursor, app)
    app.appdata["cursor_fn"] = on_move_sudoku_cursor

    def on_move_abs(y: int | None = None, x: int | None = None):
        sudoku_move_abs_cursor(app, y = y, x = x)
        app.stdwin.refresh()

    mv_first = partial(on_move_abs, x = 0)
    app.stdwin.add_mapping(tui.askey("H"), mv_first)
    app.stdwin.add_mapping(tui.askey("KEY_HOME"), mv_first)

    mv_last = partial(on_move_abs, x = 8)
    app.stdwin.add_mapping(tui.askey("L"), mv_last)
    app.stdwin.add_mapping(tui.askey("KEY_END"), mv_last)

    mv_bottom = partial(on_move_abs, y = 8)
    app.stdwin.add_mapping(tui.askey("J"), mv_bottom)
    app.stdwin.add_mapping(tui.askey("KEY_NPAGE"), mv_bottom)

    mv_top = partial(on_move_abs, y = 0)
    app.stdwin.add_mapping(tui.askey("K"), mv_top)
    app.stdwin.add_mapping(tui.askey("KEY_PPAGE"), mv_top)

    def on_delete():
        sudoku_del(app)
        app.stdwin.refresh()

    app.stdwin.add_mapping(tui.askey("KEY_BACKSPACE"), on_delete)
    app.stdwin.add_mapping(tui.askey("KEY_DC"), on_delete)
    app.stdwin.add_mapping(tui.askey("."), on_delete)

    def on_toggle_notes():
        sudoku_toggle_note_mode(app.puzzle)
        app.stdwin.refresh()

    app.stdwin.add_mapping(tui.askey("n"), on_toggle_notes)
    app.stdwin.add_mapping(tui.askey("0"), on_toggle_notes)
    app.stdwin.add_mapping(tui.askey("KEY_IC"), on_toggle_notes)

    def on_digit(digit: int):
        sudoku_ins(app, digit)
        app.stdwin.refresh()

    for digit in range(1, 10):
        app.stdwin.add_mapping(tui.askey(str(digit)), partial(on_digit, digit))

    on_post_restore = partial(sudoku_restore, app, on_move_sudoku_cursor)
    QUIT_CONFIRM_MSG = "Are you sure you want to quit?"
    QUIT_CONFIRM_ITMS = (("Yes", app.stdwin.quit), ("&No",))
    QUIT_CONFIRM_KWARGS = {
            "selection": 1,
            "info": ["This will lose any progress you've made."],
            "on_map": partial(map_base, app)}

    def on_quit():
        restore_cursor = app.puzzle.cursor
        restore_mode = app.puzzle.mode
        app.puzzle.cursor = (-1, -1)
        app.puzzle.mode = 0
        fn = partial(on_post_restore, restore_cursor, restore_mode)
        app.on_overlay_confirm(fn, QUIT_CONFIRM_MSG, *QUIT_CONFIRM_ITMS, **QUIT_CONFIRM_KWARGS)

    app.stdwin.add_mapping(tui.askey("q"), on_quit)
# }}}

def confirm_draw(app: SudokuApp, win: curses.window):# {{{
    pv = app.overlay_view
    overlay: Overlay = app.appdata.get("overlay", None)
    assert overlay is not None
    win.erase()
    padding = 1
    maxy, maxx = win.getmaxyx()
    maxx = min(maxx, curses.COLS - (padding * 2) - 1)

    msg = pad_text(overlay.message[:maxx], padding)
    info = [line[:maxx] for line in overlay.info]

    h = len(info) + 3 + (padding * 2)
    w = max(len(msg), max(len(line) for line in info)) + (padding * 2)

    tui.draw_box(win, 0, 0, h, w, ATTR_NORMAL)
    win.addstr(padding, (w - len(msg)) // 2, msg, ATTR_NORMAL)

    GAP_SENTINEL = object()
    cursor_pre = ("> ", ATTR_NORMAL)
    cursor_post = (" <", ATTR_NORMAL)
    nocurs_pre = ("  ", ATTR_NORMAL)
    nocurs_post = ("  ", ATTR_NORMAL)

    rendered = []
    rendered_width = 0
    rendered_starts = []
    for index, item in enumerate(overlay.items):
        text = item.text
        if overlay.selection == index and text[0] == '&':
            rendered.append(GAP_SENTINEL)
            rendered.append(cursor_pre)
            rendered.append((text[1], ATTR_UNDER))
            rendered.append((text[2:], ATTR_NORMAL))
            rendered.append(cursor_post)
            rendered_starts.append(rendered_width)
            rendered_width += len(text) + 3

        elif overlay.selection == index:
            rendered.append(GAP_SENTINEL)
            rendered.append(cursor_pre)
            rendered.append((text, ATTR_NORMAL))
            rendered.append(cursor_post)
            rendered_starts.append(rendered_width)
            rendered_width += len(text) + 4

        elif text[0] == '&':
            rendered.append(GAP_SENTINEL)
            rendered.append(nocurs_pre)
            rendered.append((text[1], ATTR_UNDER))
            rendered.append((text[2:], ATTR_NORMAL))
            rendered.append(nocurs_post)
            rendered_starts.append(rendered_width)
            rendered_width += len(text) + 3

        else:
            rendered.append(GAP_SENTINEL)
            rendered.append(nocurs_pre)
            rendered.append((text, ATTR_NORMAL))
            rendered.append(nocurs_post)
            rendered_starts.append(rendered_width)
            rendered_width += len(text) + 4

    y = padding + 2
    for line in info:
        win.addstr(y, (w - len(line)) // 2, line, ATTR_NORMAL)
        y += 1

    gaplen = (w - rendered_width) // (len(overlay.items) + 1)
    gap = " " * gaplen
    y += 1
    x = 1
    for item in rendered:
        if item is GAP_SENTINEL:
            win.addstr(y, x, gap, ATTR_NORMAL)
            x += gaplen
        else:
            text, attr = item
            win.addstr(y, x, text, attr)
            x += len(text)

    sy = (curses.LINES - h) // 2
    sx = (curses.COLS - w) // 2
    pv.desired_view_size = (h, w - 1)
    pv.desired_screen_start = (sy, sx)
    selection = overlay.selection
    app.stdwin.stdcurs.cursor = (sy + y, sx + rendered_starts[selection] + (gaplen * (selection + 1)) + 3)
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

ACCEL_KEYS_BLACKLIST = 'hjkl'
def overlay_accel_keys(overlay: Overlay) -> list[tuple[str, Callable[[], None]]]:# {{{
    accel_keys = []
    for item in overlay.items:
        if item.text[0] == '&':
            accel_keys.append((item.text[1].lower(), item.callback))
    return accel_keys
# }}}

def overlay_confirm(app: SudokuApp, post_restore: Callable[[], None], msg: str, *items, selection: int | None = None, info: list[str] | None = None, on_map: Callable[[], None] | None = None) -> Overlay:# {{{
    '''items are tuples of (text, callback) or (text,), the latter of which
    will assigned the callback to quit the overlay and restore the display

    Calls app.stdwin.refresh()'''

    windraw = app.overlay
    pv = app.overlay_view

    assert windraw.on_draw is None
    dp = tui.DisplayRestore(app.stdwin, windraw, pv, post_restore)
    app.stdwin.keymap = collections.OrderedDict()
    app.appdata["cursor_fn"] = partial(confirm_move_cursor, app.appdata)

    on_confirm_restore = partial(tui.display_restore, dp)
    overlay = Overlay(msg)
    for item in items:
        if len(item) == 1:
            overlay.items.append(OverlayItem(item[0], on_confirm_restore))
        else:
            text, callback = item
            overlay.items.append(OverlayItem(text, callback))

    if selection is not None:
        overlay.selection = selection

    if info is not None:
        overlay.info = info

    app.appdata["overlay"] = overlay
    windraw.on_draw = partial(confirm_draw, app)

    if on_map is not None:
        on_map()

    on_select = partial(confirm_select_cursor, app.appdata)
    app.stdwin.add_mapping(tui.askey("KEY_ENTER"), on_select)
    app.stdwin.add_mapping(tui.askey("C-J"), on_select)

    for key, callback in overlay_accel_keys(overlay):
        if key not in ACCEL_KEYS_BLACKLIST:
            app.stdwin.add_mapping(tui.askey(key), callback)

    app.stdwin.refresh()
# }}}

EXAMPLE_PUZZLE = "6...5...7 .9.1..3.. 7..6..94. 8..34.1.. ...5.1... ..5.87..9 .68..2..4 ..1..6.9. 3...9...1"
PUZZLE_SOLUTION = ""

def main(stdwin: tui.MainWindow):
    puzzle_input = EXAMPLE_PUZZLE
    app = SudokuApp(stdwin, puzzle_input)

    app.debug_vals['sg'] = partial(tui.padview_clamp, app.small_sudoku_view)
    app.debug_vals['bg'] = partial(tui.padview_clamp, app.big_sudoku_view)

    stdwin.stdcurs.cursor = (-1, -1)
    app.reset_statusbar()
    resize_gridviews(app)
    stdwin.refresh()

    map_base(app)
    map_sudoku(app)

    stdwin.mainloop()

if __name__ == "__main__":
    curses.wrapper(tui.start_curses, init_curses, main)

# vim: foldmethod=marker
