"""inbox-planner: turn a read-only inbox into a plan for the day."""

from importlib.metadata import version

__version__ = version("inbox-planner")


def main() -> None:
    """Command-line entry point. Subcommands arrive in later steps."""
    print(f"inbox-planner {__version__}")
