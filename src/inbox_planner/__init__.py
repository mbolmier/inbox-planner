"""inbox-planner: turn a read-only inbox into a plan for the day."""

from importlib.metadata import version

__version__ = version("inbox-planner")


def main() -> int:
    """Console entry point; the commands live in inbox_planner.cli."""
    from inbox_planner.cli import main as cli_main

    return cli_main()
