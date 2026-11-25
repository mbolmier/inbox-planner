import inbox_planner
from inbox_planner.cli import main


def test_without_command_the_cli_prints_its_version(capsys):
    assert main([]) == 0
    assert f"inbox-planner {inbox_planner.__version__}" in capsys.readouterr().out
