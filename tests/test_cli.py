from inbox_planner.cli import main


def test_plan_command_shows_the_demo_week_from_recorded_answers(capsys):
    assert main(["plan", "--energy", "creve,normal,forme,normal,normal,off,normal"]) == 0
    out = capsys.readouterr().out

    assert "Lundi 26/10 · énergie Crevé · travail prévu 1 h / 2 h" in out
    assert (
        "Mercredi 28/10 · énergie En forme · travail prévu 4 h 30 / 6 h" in out
    )  # spread by energy
    assert "Samedi 31/10 · énergie Off · travail prévu 0 h / 0 h" in out
    assert "07:30-16:00  RDV      Randonnée à Blue Pool" in out  # -07:00 on Saturday
    assert "14:00-17:00  RDV      Séance de travail" in out  # -08:00 on Sunday, still 14:00 local
    assert "CONFLITS" in out  # the moved lab is still repeated on Thursday (known limit)


def test_unknown_energy_is_refused(capsys):
    try:
        main(["plan", "--energy", "sleepy"])
    except SystemExit as exit:
        assert exit.code == 2
    assert "unknown energy" in capsys.readouterr().err
