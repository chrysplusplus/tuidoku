#!/usr/bin/env python3

"""
# TODO

- refine game controls
- implement grid scrolling
- implement puzzle generation
- implement undo
- implement line and box guides
"""

import curses

from dataclasses import dataclass
from functools import partial
from itertools import repeat
from typing import Callable

import tui

from util import clamp

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
    pv: tui.PadView
    sy: int

def init_curses(stdscr):# {{{
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
ATTR_PROV: int      # initialised by init_curses
ATTR_NOTE_CURS: int # initialised by init_curses
def cell_attr(y: int, x: int, cell: GridCell, sudoku: SudokuGrid) -> int: # {{{
    at_cursor = (y, x) == sudoku.cursor
    note_mode = sudoku.mode == SUDOKU_MODE_NOTE

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

def draw_big_grid(win: curses.window, grid_state: GridDrawState):# {{{
    CELL_H, CELL_W = LARGE_GRID_CELL_SIZE
    grid_state.pv.desired_view_size = LARGE_GRID_SIZE
    _, w = grid_state.pv.desired_view_size
    grid_state.pv.desired_screen_start = (grid_state.sy, (curses.COLS - w) // 2)

    tui.win_addlines(win, LARGE_GRID)

    cy, cx = grid_state.puzzle.cursor

    for i, cell in enumerate(grid_state.puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_big_grid_coords((y, x))
        attr = cell_attr(y, x, cell, grid_state.puzzle)

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

def scale_small_grid_coords(coords: tuple[int, int]) -> tuple[int, int]:# {{{
    y, x = coords
    return (2 * y + 1, 4 * x + 2)
# }}}

def draw_small_grid(win: curses.window, grid_state: GridDrawState):# {{{
    grid_state.pv.pad_start = (0, 0)
    sx = (curses.COLS - SMALL_GRID_SIZE[1]) // 2
    grid_state.pv.desired_screen_start = (grid_state.sy, sx)
    grid_state.pv.desired_view_size = SMALL_GRID_SIZE

    tui.win_addlines(win, SMALL_GRID)

    for i, cell in enumerate(grid_state.puzzle.grid):
        y, x = divmod(i, 9)
        cur_y, cur_x = scale_small_grid_coords((y, x))
        attr = ATTR_PROV if cell.provided else ATTR_NORMAL
        digit = str(cell.num) if cell.num is not None else ' '

        win.addstr(cur_y, cur_x, digit, attr)
# }}}

def sudoku_draw(cursor: tui.Cursor, prog: dict, pv: tui.PadView, reset_statusbar: Callable[[], None], win: curses.window) -> bool:# {{{
    win.erase()
    if is_small_screen(prog, reset_statusbar):
        return True

    puzzle = prog.get("puzzle", None)
    assert puzzle is not None
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
        "-- NORMAL --", "-- NOTE --" ]
MAX_MODE_STRING = len(MODE_STRINGS)
# }}}

def sudoku_def_display_mode(sudoku: SudokuGrid) -> Callable[[], str]:# {{{
    return lambda: MODE_STRINGS[clamp(sudoku.mode, MAX_MODE_STRING, 0)]
# }}}

# TODO refactor as Actions
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

# TODO refactor as Actions
def sudoku_del(sudoku: SudokuGrid):# {{{
    cy, cx = sudoku.cursor
    i = 9 * cy + cx
    if sudoku.grid[i].provided: return
    if sudoku.mode == SUDOKU_MODE_NORMAL:
        sudoku.grid[i].num = None
    elif sudoku.mode == SUDOKU_MODE_NOTE and sudoku.grid[i].num is not None:
        sudoku.grid[i].num = None
    elif sudoku.mode == SUDOKU_MODE_NOTE:
        sudoku.grid[i].notes = tuple()
# }}}

def sudoku_toggle_note_mode(sudoku: SudokuGrid):# {{{
    sudoku.mode = SUDOKU_MODE_NORMAL if sudoku.mode == SUDOKU_MODE_NOTE else SUDOKU_MODE_NOTE
# }}}

def titlebar_draw(win: curses.window) -> bool:# {{{
    win.erase()
    _, maxx = win.getmaxyx()
    text = "SUDOKU"[:maxx + 1]
    win.addstr(0, (maxx - len(text)) // 2, text)
    return True
# }}}

def statusbar_draw(prog: dict, win: curses.window) -> bool:# {{{
    status_fn = prog.get("status_fn", lambda: "")
    win.mvwin(curses.LINES - 1, 0)
    _, maxx = win.getmaxyx()
    win.erase()
    txt = status_fn()
    win.addstr(txt[:maxx + 1])
    return True
# }}}

def statusbar_reset(prog: dict):# {{{
    prog['status_fn'] = prog.get("default_status_fn", None)
# }}}

def display_screen_size() -> str:# {{{
    return f" {curses.LINES}, {curses.COLS}"
# }}}

EXAMPLE_PUZZLE = "6...5...7 .9.1..3.. 7..6..94. 8..34.1.. ...5.1... ..5.87..9 .68..2..4 ..1..6.9. 3...9...1"
PUZZLE_SOLUTION = ""

def main(stdwin: tui.MainWindow):
    puzzle: SudokuGrid = grid_from_str(EXAMPLE_PUZZLE, provided = True)
    stddraw = stdwin.stddraw
    stdscr = stdwin.stdscr

    prog = {
            "default_status_fn": sudoku_def_display_mode(puzzle),
            "sudoku_draw_last_err": False,
            "puzzle": puzzle,
            }
    prog['status_fn'] = prog['default_status_fn']

    reset_statusbar = partial(statusbar_reset, prog)

    sudoku_grid = curses.newpad(100, 100)
    sudoku_view = tui.PadView(sudoku_grid, (0, 0), (2, 0), SMALL_GRID_SIZE)
    sudoku_windraw = tui.WindowDrawState(sudoku_grid)
    sudoku_windraw.on_draw = partial(sudoku_draw, stdwin.stdcurs, prog, sudoku_view, reset_statusbar)
    stdwin.add_child(sudoku_windraw, sudoku_view)

    titlebar_win = curses.newwin(1, curses.COLS, 0, 0)
    titlebar = tui.WindowDrawState(titlebar_win)
    titlebar.on_draw = titlebar_draw
    stdwin.add_child(titlebar)

    statusbar_win = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    statusbar = tui.WindowDrawState(statusbar_win)
    statusbar.on_draw = partial(statusbar_draw, prog)
    stdwin.add_child(statusbar)

    tui.windraw_refresh(stddraw)

    stdwin.add_mapping(tui.askey("KEY_RESIZE"), stdwin.refresh)

    stdwin.add_mapping(tui.askey("q"), stdwin.quit)
    stdwin.add_mapping(tui.askey("C-C"), stdwin.quit)

    def on_reset():
        stdscr.clear()
        reset_statusbar()
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("C-L"), on_reset)

    def on_set_big_grid():
        puzzle.use_big_grid = True
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("+"), on_set_big_grid)
    stdwin.add_mapping(tui.askey("="), on_set_big_grid)

    def on_set_small_grid():
        puzzle.use_big_grid = False
        stdwin.refresh()

    stdwin.add_mapping(tui.askey("-"), on_set_small_grid)

    def on_move_rel(y = 0, x = 0):
        if sudoku_move_rel_cursor(puzzle, y = y, x = x):
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

    def on_move_abs(y: int | None = None, x: int | None = None):
        sudoku_move_abs_cursor(puzzle, y = y, x = x)
        stdwin.refresh()

    mv_first = partial(on_move_abs, x = 0)
    stdwin.add_mapping(tui.askey("H"), mv_first)
    stdwin.add_mapping(tui.askey("KEY_HOME"), mv_first)

    mv_last = partial(on_move_abs, x = 8)
    stdwin.add_mapping(tui.askey("L"), mv_last)
    stdwin.add_mapping(tui.askey("KEY_END"), mv_last)

    mv_bottom = partial(on_move_abs, y = 0)
    stdwin.add_mapping(tui.askey("J"), mv_bottom)
    stdwin.add_mapping(tui.askey("KEY_NPAGE"), mv_bottom)

    mv_top = partial(on_move_abs, y = 8)
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

    stdwin.mainloop()

if __name__ == "__main__":
    curses.wrapper(tui.start_curses, init_curses, main)

# vim: foldmethod=marker
