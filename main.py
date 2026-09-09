"""WSGI entry point for hosts that run gunicorn from the command line.

The panel's canonical entry point is ``app.py`` (``python app.py`` boots
gunicorn in-process from its ``__main__`` block). Some container /
push-to-deploy platforms instead start gunicorn themselves and expect an
app module named ``main`` (i.e. ``gunicorn main:app``).

Importing this module:

* re-exports the Flask WSGI callable ``app`` (so ``gunicorn main:app`` works)
* runs the one-time ``bootstrap()`` (schema migration + boot hooks) that the
  ``python app.py`` path normally performs, guarded by a lock file so
  concurrent gunicorn workers never migrate the database at the same time.
"""

import fcntl
import os
import time

from app import app  # noqa: F401  (WSGI callable: gunicorn main:app)


def _bootstrap_once() -> None:
    from app import SchemaMigrationError, bootstrap

    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    lock_path = os.path.join(instance_dir, ".bootstrap.lock")

    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        app.logger.exception("bootstrap skipped: cannot open lock file %s", lock_path)
        return

    deadline = time.time() + 120.0
    acquired = False
    try:
        # Wait (up to 120s) for another process/worker to finish bootstrap,
        # then run it once. The migrations are idempotent, so re-running them
        # on a fresh worker import is safe.
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.time() >= deadline:
                    app.logger.warning(
                        "bootstrap lock still busy after 120s; serving anyway"
                    )
                    return
                time.sleep(0.5)
        try:
            bootstrap()
        except SchemaMigrationError as exc:
            # Parity with the `python app.py` path: fail fast on schema errors.
            app.logger.critical(
                "Refusing to start: the database schema could not be migrated: %s",
                exc,
            )
            raise SystemExit(1)
        except Exception as exc:
            app.logger.exception("bootstrap failed: %s", exc)
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


_bootstrap_once()
