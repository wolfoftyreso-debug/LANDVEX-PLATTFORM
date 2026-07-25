#!/usr/bin/env python3
"""LANDVEX sandbox launcher - foolproof local start.

    Windows:      double-click START-WINDOWS.bat   (or: py run.py)
    macOS/Linux:  python3 run.py

Picks a free port, starts the dependency-free engine, opens the API console.
No installs, no external network. Ctrl+C to stop.

Deliberately ASCII-only in its output: a legacy Windows console (cp1252)
raises UnicodeEncodeError on arrows and dashes when stdout is redirected,
and a launcher must never fail on its own banner.
"""
import os
import socket
import sys
import threading
import webbrowser

WINDOWS = os.name == "nt"


def bail(message):
    """Exit with a message the user can actually read.

    On Windows a double-clicked window closes the instant the process ends,
    taking the error with it - so hold it open until a key is pressed.
    """
    print("\n  " + message + "\n")
    if WINDOWS:
        try:
            input("  Press Enter to close this window...")
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(1)


if sys.version_info < (3, 11):
    bail("LANDVEX needs Python 3.11 or newer. You have "
         + sys.version.split()[0] + ".\n"
         "  Install it from https://python.org/downloads and run this again.\n"
         "  On Windows, tick 'Add python.exe to PATH' in the installer.")

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

if not os.path.isdir(os.path.join(HERE, "engine")):
    bail("This launcher must sit next to the 'engine' folder.\n"
         "  Unzip the whole archive first, keep the files together,\n"
         "  then start it from inside the unzipped folder.")

os.environ.setdefault("LANDVEX_DB", "off")     # sandbox: no database file
# Bind to loopback only: the sandbox is for this machine, and on Windows it
# keeps the Firewall dialog from appearing at all.
os.environ.setdefault("LANDVEX_HOST", "127.0.0.1")

port = 8000
last_error = None
while port < 8040:
    s = socket.socket()
    try:
        # Without SO_EXCLUSIVEADDRUSE, Windows lets a bind "succeed" on a port
        # another server already holds; ask for exclusive use so a busy port
        # is reported as busy and the scan moves on.
        if WINDOWS and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", port))
        break
    except OSError as e:
        last_error = e
        port += 1
    finally:
        try:
            s.close()
        except OSError:
            pass
else:
    bail("No free port between 8000 and 8039 (last error: %s).\n"
         "  Close whatever is using them, or set LANDVEX_PORT yourself."
         % last_error)

os.environ["LANDVEX_PORT"] = str(port)

url = "http://localhost:%d/sandbox" % port
print("")
print("  LANDVEX sandbox is starting...")
print("  Console:  %s" % url)
print("  Portal:   http://localhost:%d/" % port)
print("  (Press Ctrl+C to stop)")
print("")
threading.Timer(1.2, lambda: webbrowser.open(url)).start()

import runpy  # noqa: E402 - after the environment is prepared

try:
    runpy.run_module("api.dev_server", run_name="__main__")
except KeyboardInterrupt:
    print("\n  Stopped.\n")
except Exception as e:  # noqa: BLE001 - the window must not vanish silently
    bail("The engine failed to start: %s: %s" % (type(e).__name__, e))
