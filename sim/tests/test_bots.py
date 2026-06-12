"""Bot harness and bot sanity checks (DESIGN.md §4).

Covers: the D11 +1 µs injection rule and strict monotonicity in harness
runs, common-random-numbers reproducibility, Bot 0 semantics, Bot 1
posterior health and quote validity, and that every harness round holds
the §2.2 identities (score_round raises otherwise).
"""

import numpy as np
import pytest

from picked_off.bots.base import run_bot
from picked_off.bots.bot0 import Bot0
from picked_off.bots.bot1 import Bot1
from picked_off.bots.bot2 import Bot2
from picked_off.generator import generate_stream
from picked_off.params import TICK_GRID_US, SimParams
from picked_off.scoring import score_round

PARAMS = SimParams()


def _stream(seed, params=PARAMS):
    return generate_stream(params, seed, None)


def test_harness_injection_timestamps_are_legal():
    events = _stream(0)
    result = run_bot(PARAMS, events, Bot0())
    exo_times = {ev.t_us for ev in events}
    quote_times = [q.t_us for q in result.quotes]
    assert quote_times[0] == 0  # opening quote from on_start
    assert quote_times == sorted(quote_times)
    assert len(set(quote_times)) == len(quote_times)
    for t in quote_times[1:]:
        assert t not in exo_times  # never ties an exogenous event (D11)
        # injected at decision_time + 1: decision was a tick or a fill
        assert (t - 1) % TICK_GRID_US == 0 or (t - 1) in exo_times
    score_round(result)  # identities hold in harness mode


def test_bot0_semantics():
    bot = Bot0(k0=3)
    assert bot.on_start(PARAMS) == (PARAMS.v0 - 3, PARAMS.v0 + 3)
    assert bot.on_fill(1_000_003, "buy", 10_003) == (10_000, 10_006)  # mid -> last fill
    assert bot.on_tick(1_100_000) == (10_000, 10_006)  # idempotent between fills


def test_common_random_numbers_same_stream_same_result():
    events = _stream(5)
    r1 = run_bot(PARAMS, events, Bot0())
    r2 = run_bot(PARAMS, events, Bot0())
    assert [f.t_us for f in r1.fills] == [f.t_us for f in r2.fills]
    assert (r1.cash, r1.inventory) == (r2.cash, r2.inventory)


@pytest.mark.parametrize("bot_cls", [Bot1, Bot2])
def test_bayesian_bot_round_is_healthy(bot_cls):
    bot = bot_cls()
    result = run_bot(PARAMS, _stream(11), bot)
    score_round(result)  # identities hold
    # Posterior stays a distribution on the grid.
    assert np.isclose(bot.pi.sum(), 1.0)
    assert (bot.pi >= 0).all()
    # All quotes the bot ever posted were valid integers, uncrossed.
    for q in result.quotes:
        assert isinstance(q.bid, int) and isinstance(q.ask, int)
        assert q.ask >= q.bid + 1


def test_bot1_learns_from_fills():
    """After one-sided buy flow, Bot 1's posterior mean must move up.

    Needs lambda_j > 0 so the prior has diffused off the V0 point mass
    (a point-mass prior correctly attributes any fill to noise: informed
    buys require V > ask, which has prior probability zero there).
    """
    params = SimParams(alpha=0.6, lambda_j=0.5)
    bot = Bot1()
    bot.on_start(params)
    bot.on_tick(1_000_000)  # diffuse the posterior
    mean_before = float(bot.values @ bot.pi)
    t = 1_150_003
    for _ in range(5):
        bot.on_fill(t, "buy", bot.ask)
        t += 250_007
    mean_after = float(bot.values @ bot.pi)
    assert mean_after > mean_before + 1.0


class _AlwaysMovingBot:
    """Stub that changes quotes at every callback: exercises tick injection."""

    def on_start(self, params):
        self.mid = params.v0
        return self.mid - 3, self.mid + 3

    def on_fill(self, t_us, side, price):
        self.mid = price + 1
        return self.mid - 3, self.mid + 3

    def on_tick(self, t_us):
        self.mid += 1
        return self.mid - 3, self.mid + 3


def test_harness_injection_paths_hand_built():
    """The D11 collision cases (base.py docstring): a fill at k*G-1 whose
    injected quote lands ON the tick grid, the tick's own injection at
    grid+1, and the end-of-round injection skip."""
    from picked_off.events import ArrivalEvent
    from picked_off.params import SimParams as SP

    G = TICK_GRID_US
    params = SP(lambda_a=0.0, lambda_j=0.0)
    exo = [
        ArrivalEvent(5 * G - 1, "noise", "buy", 0.0),  # always fills (u=0 < f)
        ArrivalEvent(5 * G + 2, "noise", "sell", 0.0),
        ArrivalEvent(params.round_us - 1, "noise", "buy", 0.0),  # injection must be skipped
    ]
    result = run_bot(params, exo, _AlwaysMovingBot())
    score_round(result)
    quote_times = [q.t_us for q in result.quotes]
    assert quote_times == sorted(quote_times) and len(set(quote_times)) == len(quote_times)
    assert 5 * G in quote_times  # fill at 5G-1 -> injected quote ON the grid point
    assert 5 * G + 1 in quote_times  # the tick at 5G injects at grid+1
    assert all(t < params.round_us for t in quote_times)  # last-µs injection skipped
    assert len(result.fills) == 3


def test_harness_rejects_malformed_streams():
    from picked_off.events import ArrivalEvent, JumpEvent, StreamError

    bot = Bot0()
    with pytest.raises(StreamError):  # non-monotone must fail loudly, not re-sort
        run_bot(PARAMS, [JumpEvent(5_000_003, 4), JumpEvent(2_000_003, -2)], bot)
    with pytest.raises(ValueError, match="hygiene"):  # tick-grid arrival
        run_bot(PARAMS, [ArrivalEvent(TICK_GRID_US, "informed", None, None)], bot)
    with pytest.raises(ValueError, match="hygiene"):  # consecutive µs
        run_bot(
            PARAMS,
            [JumpEvent(500_003, 1), JumpEvent(500_004, 1)],
            bot,
        )


def test_harness_rejects_non_integer_quotes():
    class FloatBot:
        def on_start(self, params):
            return params.v0 - 2.5, params.v0 + 2.5

        def on_fill(self, t_us, side, price):
            return 0, 1

        def on_tick(self, t_us):
            return 0, 1

    with pytest.raises(ValueError, match="non-integer"):
        run_bot(PARAMS, _stream(0), FloatBot())


def test_bot1_handles_p_jump_one():
    params = SimParams(p_jump=1.0)
    bot = Bot1()
    bot.on_start(params)
    bot.on_tick(1_000_000)  # kernel is {-1: .5, +1: .5}; must not crash
    assert np.isclose(bot.pi.sum(), 1.0)


def test_bot2_skew_rounds_half_away_from_zero():
    from picked_off.bots.bot2 import _round_half_away

    assert _round_half_away(0.5) == 1 and _round_half_away(-0.5) == -1
    assert _round_half_away(1.5) == 2 and _round_half_away(-1.5) == -2
    assert _round_half_away(0.0) == 0
    # One customer sell -> dealer inventory +1 -> skew must be -1 tick, not 0
    # (banker's rounding would give 0). Bot1 and Bot2 see identical inputs up
    # to and including the first fill, so Bot2 == Bot1 shifted by -1.
    bot2 = Bot2(gamma=0.5)
    b2_open = bot2.on_start(PARAMS)
    bot1 = Bot1()
    b1_open = bot1.on_start(PARAMS)
    assert b2_open == b1_open  # zero inventory -> zero skew
    price = b2_open[0]  # customer sells at the standing bid
    q1 = bot1.on_fill(500_003, "sell", price)
    q2 = bot2.on_fill(500_003, "sell", price)
    assert bot2.inv == 1
    assert q2 == (q1[0] - 1, q1[1] - 1)
    assert (bot2.bid, bot2.ask) == q2  # posterior conditions on skewed quotes


def test_bot1_widens_with_alpha_on_fixed_posterior():
    """On the SAME dispersed posterior, more informed flow -> wider quotes.

    (The comparative static must be tested on a fixed posterior: in a live
    round, higher alpha also makes silence more informative, which tightens
    the posterior and can legitimately tighten quotes.)
    """
    spreads = []
    for alpha in (0.05, 0.5):
        params = SimParams(alpha=alpha)
        bot = Bot1()
        bot.on_start(params)
        # Hand-set a dispersed posterior (discretized double exponential, scale 10).
        dist = np.exp(-np.abs(bot.values - params.v0) / 10.0)
        bot.pi = dist / dist.sum()
        bid, ask = bot._regret_free()
        spreads.append(ask - bid)
    assert spreads[1] > spreads[0]
