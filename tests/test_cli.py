from inbox_planner.cli import main


def test_plan_command_shows_the_demo_week_from_recorded_answers(capsys):
    assert main(["plan", "--energy", "creve,normal,forme,normal,normal,off,normal"]) == 0
    out = capsys.readouterr().out

    assert "Lundi 26/10 · énergie Crevé · travail prévu 2 h / 2 h" in out
    assert "Samedi 31/10 · énergie Off · travail prévu 0 h / 0 h" in out
    assert "10:00-11:00  RDV      Appel avec" in out  # 19:00 in Paris on 1 November
    assert "CONFLITS" in out  # the moved lab is still repeated on Thursday (known limit)


def test_unknown_energy_is_refused(capsys):
    try:
        main(["plan", "--energy", "sleepy"])
    except SystemExit as exit:
        assert exit.code == 2
    assert "unknown energy" in capsys.readouterr().err
