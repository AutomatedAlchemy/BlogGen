#!/usr/bin/env python3
"""Interactive test harness for the BlogGen 3-button terminal menu.

This does NOT re-implement the menu. It imports the real functions from
``main.py`` and wraps them with logging shims so the *actual* loop logic under
test (`main.run_interactive_loop`) runs unchanged — hover regions, mouse mode
1003, index arithmetic, keyboard handling, all of it. Every raw input event,
mouse parse, action fire and menu redraw is appended to a debug log so the
behavior can be inspected after the fact (e.g. by another tool reading the file).

Run it in a real terminal (it needs a tty):

    python3 test_menu.py                 # log -> ./menu_debug.log
    python3 test_menu.py /tmp/foo.log    # custom log path

Then move the mouse over the three buttons (hover should change the highlight),
use arrows / 1-2-3 / clicks, and pick "3. Exit" (or press q / Ctrl-C) to quit.
The log records what the menu actually did for each event.
"""
import os
import sys
import functools

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import main  # noqa: E402  (real implementation under test)

LOG_PATH = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "menu_debug.log")

# Fresh log each run.
_log_fh = open(LOG_PATH, "w", encoding="utf-8", buffering=1)


def log(msg):
    """Write a line to the debug log (line-buffered, so tail -f works live)."""
    _log_fh.write(msg + "\n")
    _log_fh.flush()


def _repr_seq(seq):
    """Human-readable repr of a raw input event (escape bytes shown)."""
    return repr(seq)


# ---- shims over the real menu primitives -----------------------------------

_orig_read_input_event = main.read_input_event
_orig_parse_sgr_mouse = main.parse_sgr_mouse
_orig_draw_menu = main.draw_menu

# Track the last-drawn selection so hover changes are obvious in the log.
_state = {"last_active": None, "events": 0, "hover_changes": 0, "redraws": 0}


@functools.wraps(_orig_read_input_event)
def read_input_event():
    seq = _orig_read_input_event()
    if seq:
        _state["events"] += 1
        log(f"[EVENT #{_state['events']:04d}] raw={_repr_seq(seq)}")
    return seq


@functools.wraps(_orig_parse_sgr_mouse)
def parse_sgr_mouse(seq):
    parsed = _orig_parse_sgr_mouse(seq)
    if parsed:
        pb, px, py, is_press = parsed
        kind = "PRESS/BTN" if pb < 32 else "MOTION"
        log(f"    mouse: button={pb} col={px} row={py} "
            f"is_press={is_press} ({kind})")
    return parsed


@functools.wraps(_orig_draw_menu)
def draw_menu(R_start, active_index):
    _state["redraws"] += 1
    if active_index != _state["last_active"]:
        prev = _state["last_active"]
        _state["last_active"] = active_index
        if prev is not None:
            _state["hover_changes"] += 1
        names = ["Enter Prompt", "Take Screenshot", "Exit"]
        log(f"    -> SELECTION now [{active_index}] {names[active_index]} "
            f"(was {prev}); redraw #{_state['redraws']} at row {R_start}")
    return _orig_draw_menu(R_start, active_index)


def handle_action(action_idx, chat, last_image_filename, combined_name, R_start, old_settings):
    """Stub: log the fired action instead of generating a blogpost.

    Restores the terminal the same way the real handler does (disables mouse
    tracking + restores cooked mode) so the loop can cleanly re-arm afterward.
    Returns break_loop=True only for Exit (idx 2) so the test can quit that way.
    """
    names = ["Enter Prompt", "Take Screenshot", "Exit"]
    log(f"### ACTION FIRED: [{action_idx}] {names[action_idx]}")
    sys.stdout.write("\033[?1003l\033[?1006l\033[?25h\n")
    sys.stdout.flush()
    import termios
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    main.flush_stdin()
    if action_idx == 2:
        print(main.colored("\n[TEST] Exit selected — quitting.", "green"))
        return True, chat
    print(main.colored(f"\n[TEST] Would run action: {names[action_idx]}. "
                       f"Returning to menu...", "yellow"))
    return False, chat


def main_test():
    if not sys.stdin.isatty():
        print("ERROR: needs an interactive terminal (tty). Run me in konsole.")
        log("ABORT: stdin is not a tty")
        return

    # Patch the real module in place.
    main.read_input_event = read_input_event
    main.parse_sgr_mouse = parse_sgr_mouse
    main.draw_menu = draw_menu
    main.handle_action = handle_action

    log("=== BlogGen menu test session start ===")
    log(f"log file: {LOG_PATH}")
    log("Instructions: hover the 3 buttons (highlight should follow the mouse),")
    log("try arrows / 1-2-3 / clicks, then pick '3. Exit' to quit.")
    log("-" * 60)

    print(main.colored("BlogGen menu test harness", "cyan", attrs=["bold"]))
    print(main.colored(f"Debug log: {LOG_PATH}", "white"))
    print(main.colored("Hover the buttons with your mouse — the highlight should "
                       "follow. Use arrows / 1-2-3 / click. Pick '3. Exit' to quit.\n",
                       "white"))

    try:
        main.run_interactive_loop(chat=None, last_image_filename="test.png",
                                  combined_name="menu_test")
    except KeyboardInterrupt:
        log("KeyboardInterrupt — user aborted")
    finally:
        log("-" * 60)
        log(f"totals: events={_state['events']} redraws={_state['redraws']} "
            f"hover/selection-changes={_state['hover_changes']}")
        log("=== session end ===")
        _log_fh.close()
        print(main.colored(f"\nDone. Debug log written to {LOG_PATH}", "green", attrs=["bold"]))


if __name__ == "__main__":
    main_test()
