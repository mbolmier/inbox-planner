import inbox_planner


def test_cli_prints_installed_version(capsys):
    inbox_planner.main()
    assert capsys.readouterr().out.strip() == f"inbox-planner {inbox_planner.__version__}"
