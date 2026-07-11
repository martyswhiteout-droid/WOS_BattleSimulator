from .candidate import CandidateModel, PowerLawKernel, SharedMechanics
from .dataset import discover_nanomart


def test_candidate_simulation_is_deterministic() -> None:
    battle = next(record for record in discover_nanomart() if record.included)
    model = CandidateModel(
        "power_law",
        PowerLawKernel(-3.0, 1.0, 1.0, 1.0, 0.0),
        SharedMechanics(1.0, 0.5, 6),
    )
    assert model.simulate(battle) == model.simulate(battle)
