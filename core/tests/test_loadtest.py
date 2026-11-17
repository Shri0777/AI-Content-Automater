"""The load test's helpers make a burst, measure it and clean up after."""

from django.contrib.auth import get_user_model

from core import loadtest
from planning.dispatcher import run_dispatcher


def test_a_small_burst_is_made_finished_measured_and_removed(db):
    run_id, plans = loadtest.make_burst(8)

    run_dispatcher()

    counts = loadtest.progress(plans)
    assert loadtest.count_finished(counts) == 8
    claim_lags, making_times = loadtest.timings(plans)
    assert len(claim_lags) == 8
    assert loadtest.database_connections() >= 1
    assert loadtest.delete_burst(run_id) == 2
    assert not get_user_model().objects.filter(email__startswith="loadtest-").exists()


def test_percentiles_pick_the_right_value():
    values = list(range(1, 101))

    assert loadtest.percentile(values, 0.5) == 51
    assert loadtest.percentile(values, 0.99) == 100
    assert loadtest.percentile([], 0.5) == 0
