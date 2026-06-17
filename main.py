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
    nums: tuple[int,...]
    provided: bool = False

@dataclass(slots = True)
class SudokuGrid:
    grid: list[GridCell]

@dataclass(slots = True)
class GridDrawState:
    puzzle: SudokuGrid
    pv: PadView
    sy: int
    cursor: tuple[int,int]

def init_curses(stdscr):
    curses.raw()
    curses.curs_set(0)
    curses.use_default_colors()

    stdscr.nodelay(True)

    # init colors
    assert curses.COLOR_PAIRS > 3
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)

    global ATTR_CUR, ATTR_PROV
    ATTR_CUR = curses.color_pair(1)
    ATTR_PROV = curses.color_pair(2)

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
def key_from_bytes(xs: list[int]) -> Key:# {{{
    assert len(xs) > 0
    x = xs[0]
    solo = len(xs) == 1
    if solo and cascii.isctrl(x):
        return Key(cascii.unctrl(x)[1], ctrl = True)

    if solo:
        return Key(bytes(curses.keyname(x)).decode("utf-8"), special = x > 127)

    if x == cascii.ESC and cascii.isctrl(xs[1]):
        return Key(cascii.unctrl(xs[1])[1], ctrl = True, alt = True)

    if x == cascii.ESC:
        return Key(bytes(xs[1:]).decode("utf-8"), alt = True)

    try:
        return Key(bytes(xs).decode("utf-8"))

    except ValueError:
        return Key(f"UNK_{xs}")
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
        return Key(upper[2], alt = True)
    return Key(ch)
# }}}
def getkbytes(stdscr: curses.window) -> list[int]:# {{{
    kbytes = []
    key = stdscr.getch()
    while key != -1:
        kbytes.append(key)
        key = stdscr.getch()
    return kbytes
# }}}
def grid_from_str(s: str) -> GridCell | None:# {{{
    grid = []
    for ch in s:
        if ch == ".":
            grid.append(GridCell(tuple()))

        elif ch.isdigit():
            grid.append(GridCell((int(ch),)))

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
LARGE_GRID = grid_lines(3, 7)
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
def stddraw_def_draw(**kwargs) -> Callable[[curses.window], bool]:# {{{
    children = kwargs.get("children", [])
    def on_draw(win: curses.window) -> bool:
        win.clear()

        win.noutrefresh()
        for child in children:
            windraw_noutrefresh(*child)

        return False

    return on_draw
# }}}
def is_small_screen(prog: dict, reset_fn: Callable[[], None]) -> bool:
    draw_errmsg = "Screen too small to display grid"
    if SMALL_GRID_SIZE[0] > curses.LINES - SUDOKU_GRID_MARGIN:
        prog["status_fn"] = lambda: draw_errmsg
        prog["sudoku_draw_last_err"] = True
        return True

    if prog.get("sudoku_draw_last_err", False): # reset if resized screen is no longer too small
        reset_fn()
        prog["sudoku_draw_last_err"] = False

    return False

ATTR_NORMAL = curses.A_NORMAL
ATTR_CUR = None
ATTR_PROV = None
def cell_attr(y: int, x: int, cell: GridCell, cursor: tuple[int,int]) -> int: # assuming curses attrs are ints
    if (y, x) == cursor:
        return ATTR_CUR
    if cell.provided:
        return ATTR_PROV
    else:
        return ATTR_NORMAL

def draw_big_grid(win: curses.window, grid_state: GridDrawState):
    grid_state.pv.desired_view_size = LARGE_GRID_SIZE
    _, w = grid_state.pv.desired_view_size
    grid_state.pv.desired_screen_start = (grid_state.sy, (curses.COLS - w) // 2)

    win_addlines(win, LARGE_GRID)

    for i, cell in enumerate(grid_state.puzzle.grid):
        if len(cell.nums) == 0: continue
        y, x = divmod(i, 9)
        attr = cell_attr(y, x, cell, grid_state.cursor)
        cur_y = 4 * y + 1
        cur_x = 8 * x + 2
        if len(cell.nums) == 1:
            digit = cell.nums[0]
            digit_lines = font_l[digit]
            for line_i, line in enumerate(digit_lines):
                win.addstr(cur_y + line_i, cur_x, line, attr)

        else:
            digits = cell.nums
            for digit in digits:
                off_y, off_x = divmod(digit - 1, 3)
                win.addstr(cur_y + off_y, cur_x + 2 * off_x, str(digit), attr)

def draw_small_grid(win: curses.window, grid_state: GridDrawState):
    grid_state.pv.pad_start = (0, 0)
    sx = (curses.COLS - SMALL_GRID_SIZE[1]) // 2
    grid_state.pv.desired_screen_start = (grid_state.sy, sx)
    grid_state.pv.desired_view_size = SMALL_GRID_SIZE

    win_addlines(win, SMALL_GRID)

    for i, cell in enumerate(grid_state.puzzle.grid):
        if len(cell.nums) != 1: continue
        digit = cell.nums[0]
        y, x = divmod(i, 9)
        attr = cell_attr(y, x, cell, grid_state.cursor)

        win.addstr(2 * y + 1, 4 * x + 2, str(digit), attr)

SUDOKU_GRID_MARGIN = 5
def sudoku_def_draw(**kwargs) -> Callable[[curses.window], bool]:
    def on_draw(win: curses.window) -> bool:
        prog = kwargs['prog']
        pv = kwargs['pv']

        win.clear()
        if is_small_screen(prog, kwargs['reset_statusbar']): return True

        puzzle = prog.get("puzzle", None)
        sy, _ = pv.desired_screen_start
        if prog.get("use_big_grid", False):
            draw_big_grid(win, GridDrawState(puzzle, pv, sy, prog.get("cursor", (0, 0))))
        else:
            draw_small_grid(win, GridDrawState(puzzle, pv, sy, prog.get("cursor", (0, 0))))

        return True

    return on_draw

def titlebar_def_draw(**kwargs) -> Callable[[curses.window], bool]:
    def on_draw(win: curses.window) -> bool:
        win.clear()
        _, maxx = win.getmaxyx()
        text = "SUDOKU"[:maxx + 1]
        win.addstr(0, (maxx - len(text)) // 2, text)
        return True

    return on_draw

def statusbar_def_draw(**kwargs) -> Callable[[curses.window], bool]:
    def on_draw(win: curses.window) -> bool:
        prog = kwargs['prog']
        status_fn = prog.get("status_fn", lambda: "")
        win.mvwin(curses.LINES - 1, 0)
        _, maxx = win.getmaxyx()
        win.clear()
        txt = status_fn()
        win.addstr(txt[:maxx + 1])
        return True

    return on_draw

def display_screen_size() -> str:
    return f" {curses.LINES}, {curses.COLS}"

def statusbar_def_reset(**kwargs) -> Callable[[], None]:
    def on_reset():
        prog = kwargs['prog']
        prog['status_fn'] = prog.get("default_status_fn", None)

    return on_reset

def clamp_cursor(cursor: tuple[int, int]) -> tuple[int, int]:
    y, x = cursor
    return (min(0, max(8, y)), max(0, max(8, x)))

EXAMPLE_PUZZLE = "6...5...7 .9.1..3.. 7..6..94. 8..34.1.. ...5.1... ..5.87..9 .68..2..4 ..1..6.9. 3...9...1"

def main(stdscr: curses.window):
    init_curses(stdscr)

    puzzle = grid_from_str(EXAMPLE_PUZZLE)
    puzzle.grid[2].nums = (2,3,4,9)
    puzzle.grid[31].provided = True

    prog = {
            "default_status_fn": display_screen_size,
            "sudoku_draw_last_err": False,
            "use_big_grid": False,
            "puzzle": puzzle,
            "cursor": (0, 0),
            }
    prog['status_fn'] = prog['default_status_fn']

    reset_statusbar = statusbar_def_reset(prog = prog)

    stddraw = WindowDrawState(stdscr)
    children = []

    sudoku_grid = curses.newpad(100, 100)
    sudoku_view = PadView(sudoku_grid, (0, 0), (1, 0), SMALL_GRID_SIZE)
    sudoku_draw = WindowDrawState(sudoku_grid)
    sudoku_draw.on_draw = sudoku_def_draw(
            pv = sudoku_view,
            prog = prog,
            reset_statusbar = reset_statusbar
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

    stddraw.on_draw = stddraw_def_draw(children = children)

    windraw_refresh(stddraw)

    while True:
        if len(kbytes := getkbytes(stdscr)) == 0: continue
        if kbytes[0] == curses.KEY_RESIZE:
            windraw_refresh(stddraw)
            continue

        key = key_from_bytes(kbytes)
        if key == askey("q"):
            break
        if key == askey("C-C"):
            break
        if key == askey("C-L"):
            reset_statusbar()
            windraw_refresh(stddraw)
            continue
        if key == askey("+") or key == askey("="):
            prog["use_big_grid"] = True
            windraw_refresh(stddraw)
            continue
        if key == askey("-"):
            prog["use_big_grid"] = False
            windraw_refresh(stddraw)
            continue
        if key == askey("h") or kbytes[0] == curses.KEY_LEFT:
            y, x = prog.get("cursor", (0, 0))
            prog["cursor"] = clamp_cursor((y, x - 1))
            windraw_refresh(stddraw)
            continue
        if key == askey("l") or kbytes[0] == curses.KEY_RIGHT:
            y, x = prog.get("cursor", (0, 0))
            prog["cursor"] = clamp_cursor((y, x + 1))
            windraw_refresh(stddraw)
            continue
        if key == askey("j") or kbytes[0] == curses.KEY_DOWN:
            y, x = prog.get("cursor", (0, 0))
            prog["cursor"] = clamp_cursor((y + 1, x))
            windraw_refresh(stddraw)
            continue
        if key == askey("k") or kbytes[0] == curses.KEY_UP:
            y, x = prog.get("cursor", (0, 0))
            prog["cursor"] = clamp_cursor((y - 1, x))
            windraw_refresh(stddraw)
            continue

if __name__ == "__main__":
    curses.wrapper(main)

# vim: foldmethod=marker
