from l0_paper.populace_smoke import make_toy_frame, make_toy_targets, run_l0_smoke


def test_toy_targets_compile_against_populace_frame():
    frame, truths = make_toy_frame(seed=1, n=30)
    targets = make_toy_targets(truths)

    assert frame.n("household") == 30
    assert len(targets) == 3


def test_l0_smoke_uses_populace_budget_control():
    summary = run_l0_smoke(seed=0, n=120, target_records=60, epochs=120)

    assert summary.final_loss < summary.initial_loss
    assert summary.n_nonzero < summary.n_records
    assert summary.l0_lambda > 0
