# Coglet RP2040 launcher (MicroPython).
#
# Keep this file tiny: it is the one piece that has to keep working for the
# ESP to be able to repair everything else. The real program is app.py.
#   1. finish an update that a power cut interrupted;
#   2. run app.py;
#   3. if app.py fails to start, stay in recovery mode so the ESP can send a
#      working version over the UART link (no USB / switch needed).
import sys
import coglet_updater

coglet_updater.finish_pending_commit()

try:
    import app  # noqa: F401  (runs Coglet; never returns)
except KeyboardInterrupt:
    raise       # Thonny / the web page stopping the program
except Exception as exc:
    sys.print_exception(exc)
    coglet_updater.recovery()
