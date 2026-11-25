"""BATON console entry point for the managed harness, Git lifecycle and verification observer."""
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["git"]:
        from .git_cli import main as git_main
        return git_main(argv[1:])
    if argv[:1] == ["verification-shadow"]:
        from .verification_shadow import main as shadow_main
        return shadow_main(argv[1:])
    from .managed_cli import main as managed_main
    try:
        return managed_main(argv)
    except SystemExit as exc:
        if exc.code == 0 and argv in (["--help"], ["-h"]):
            print("  verification-shadow    compare local verification evidence (read-only)")
        raise


if __name__ == "__main__":
    sys.exit(main())
