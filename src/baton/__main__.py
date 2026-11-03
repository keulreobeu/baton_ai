"""BATON CLI: `baton git ...` for the Git lifecycle, everything else for the managed harness."""
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["git"]:
        from .git_cli import main as git_main
        return git_main(argv[1:])
    from .managed_cli import main as managed_main
    return managed_main(argv)


if __name__ == "__main__":
    sys.exit(main())
