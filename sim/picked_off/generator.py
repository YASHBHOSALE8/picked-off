"""Seeded event-stream generation — the ONLY randomness in the project
(DESIGN.md §6.1, §6.3).

Responsibilities:
- generate_stream: Poisson(lambda_j) jumps with discrete-Laplace sizes
  (sign * Geometric(p_jump)), Poisson(lambda_a) arrivals with types, noise
  side intents and acceptance uniforms; integer-µs timestamps obeying the
  §6.3 rule 5 timestamp hygiene; optional scripted quote schedule merged in.
- certify: every check a frozen vector must pass, including the 1e-9
  |u_accept - f(h)| margin evaluated against the scripted quotes, and the
  Q5 guard that V stays strictly positive along the realized path.
- expected_output / make_vector: produce the §6.2 expected_output block by
  running the engine + scoring, and assemble complete certified vectors
  (re-rolling the seed deterministically until certification passes).

Engines never import this module's RNG; they are pure functions of streams.
"""

from __future__ import annotations

import math

import numpy as np

from .engine import noise_accept_prob, run_stream
from .events import ArrivalEvent, Event, JumpEvent, QuoteEvent, validate_stream
from .params import TICK_GRID_US, SimParams
from .scoring import score_round

#: Minimum |u_accept - f(h)| margin at every evaluated noise arrival (§6.3-2).
U_ACCEPT_MARGIN = 1e-9

#: Deterministic seed increment when a candidate stream fails certification.
SEED_RETRY_STEP = 1_000_003

#: Q5 guard: require v0 > _V_SIGMA_GUARD * (RMS of total round V drift).
_V_SIGMA_GUARD = 6.0


class CertificationError(ValueError):
    """A candidate stream/vector failed a certification check."""


def round_drift_rms(params: SimParams) -> float:
    """RMS of V_T - V0: sqrt(lambda_j * T_sec * E[J^2]), E[J^2]=(2-p)/p^2 (§1.1)."""
    t_sec = params.round_us / 1e6
    e_j2 = (2.0 - params.p_jump) / params.p_jump**2
    return math.sqrt(params.lambda_j * t_sec * e_j2)


def check_params_v_positive(params: SimParams) -> None:
    """Q5: reject parameter corners where V < 0 is plausible (> ~6 sigma rule)."""
    if params.v0 <= _V_SIGMA_GUARD * round_drift_rms(params):
        raise CertificationError(
            f"params rejected (Q5): v0={params.v0} is within {_V_SIGMA_GUARD} sigma "
            f"of round V drift ({round_drift_rms(params):.1f} ticks) — V < 0 plausible"
        )


def _hygiene_violation(t: int, occupied: set[int], quote_times: set[int]) -> bool:
    """§6.3 rule 5 for one candidate jump/arrival timestamp."""
    if t <= 1:
        return True
    if t % TICK_GRID_US in (0, 1):  # tick grid and its +1 injection slots
        return True
    if t in occupied or (t - 1) in occupied or (t + 1) in occupied:
        return True  # within 1 µs of another exogenous event
    if t in quote_times:  # never tie a scripted quote event
        return True
    return False


def generate_stream(
    params: SimParams,
    seed: int,
    quote_schedule: list[tuple[int, int, int]] | None = None,
) -> list[Event]:
    """Deterministic stream from a seed.

    quote_schedule: list of (t_us, bid, ask), strictly increasing, first at
    t_us=0 — required for vector streams. Pass None for harness streams
    (jumps/arrivals only; the bot harness injects quotes at run time).
    Raises CertificationError if the realized V path touches <= 0 (caller
    re-rolls the seed; see make_vector / next_good_seed).
    """
    check_params_v_positive(params)
    rng = np.random.default_rng(seed)
    t_sec = params.round_us / 1e6

    quote_times: set[int] = set()
    quote_events: list[QuoteEvent] = []
    if quote_schedule is not None:
        if not quote_schedule or quote_schedule[0][0] != 0:
            raise ValueError("quote_schedule must start at t_us = 0")
        last = -1
        for t, b, a in quote_schedule:
            if t <= last:
                raise ValueError("quote_schedule timestamps must be strictly increasing")
            if not (0 <= t < params.round_us):
                raise ValueError(f"quote time {t} outside round")
            last = t
            quote_times.add(t)
            quote_events.append(QuoteEvent(t, int(b), int(a)))

    occupied: set[int] = set()

    def draw_times(rate_per_s: float) -> list[int]:
        n = int(rng.poisson(rate_per_s * t_sec))
        times = []
        for _ in range(n):
            for _attempt in range(10_000):
                t = int(rng.integers(0, params.round_us))
                if not _hygiene_violation(t, occupied, quote_times):
                    break
            else:  # pragma: no cover - astronomically unlikely
                raise CertificationError("could not draw a hygienic timestamp")
            occupied.add(t)
            times.append(t)
        return sorted(times)

    jump_times = draw_times(params.lambda_j)
    jumps = []
    v_path = params.v0
    for t in jump_times:
        sign = 1 if rng.random() < 0.5 else -1
        size = sign * int(rng.geometric(params.p_jump))
        jumps.append(JumpEvent(t, size))
        v_path += size
        if v_path <= 0:
            raise CertificationError(f"realized V path hit {v_path} <= 0 at t={t} (Q5)")

    arrival_times = draw_times(params.lambda_a)
    arrivals = []
    for t in arrival_times:
        if rng.random() < params.alpha:
            arrivals.append(ArrivalEvent(t, "informed", None, None))
        else:
            side = "buy" if rng.random() < 0.5 else "sell"
            arrivals.append(ArrivalEvent(t, "noise", side, float(rng.random())))

    events = sorted(
        [*quote_events, *jumps, *arrivals],
        key=lambda ev: ev.t_us,
    )
    validate_stream(events, params.round_us, require_opening_quote=quote_schedule is not None)
    return events


def certify(params: SimParams, events: list) -> None:
    """All checks a frozen vector stream must pass (§6.3). Raises on failure."""
    from .events import event_to_json, parse_stream

    check_params_v_positive(params)
    # Round-trip through the JSON parser so every §6.2 per-event field
    # constraint (quote validity, nonzero jumps, u_accept in [0,1),
    # side_intent iff noise) is enforced as part of certification, even for
    # hand-constructed Event objects.
    events = parse_stream(
        [event_to_json(ev) for ev in events], params.round_us, require_opening_quote=True
    )

    occupied: set[int] = set()
    quote_times = {ev.t_us for ev in events if isinstance(ev, QuoteEvent)}
    v = params.v0
    quotes = None
    for ev in events:
        if isinstance(ev, QuoteEvent):
            quotes = (ev.bid, ev.ask)
            continue
        if _hygiene_violation(ev.t_us, occupied, quote_times):
            raise CertificationError(f"timestamp hygiene violation at t_us={ev.t_us} (§6.3-5)")
        occupied.add(ev.t_us)
        if isinstance(ev, JumpEvent):
            v += ev.size
            if v <= 0:
                raise CertificationError(f"V path hit {v} <= 0 at t={ev.t_us} (Q5)")
        elif isinstance(ev, ArrivalEvent) and ev.trader == "noise":
            f = noise_accept_prob(quotes[0], quotes[1], params.delta0)
            if abs(ev.u_accept - f) <= U_ACCEPT_MARGIN:
                raise CertificationError(
                    f"u_accept margin violation at t_us={ev.t_us}: |{ev.u_accept} - f={f}| <= {U_ACCEPT_MARGIN}"
                )


def expected_output(params: SimParams, events: list) -> dict:
    """Run engine + scoring and build the §6.2 expected_output block."""
    result = run_stream(params, events)
    decomp, fill_scores = score_round(result)
    fills_json = []
    for f, s in zip(result.fills, fill_scores):
        fills_json.append(
            {
                "t_us": f.t_us,
                "side": f.side,
                "price": f.price,
                "v_at_fill": f.v_at_fill,
                "trader": f.trader,
                "markout_1s": s.markout_1s,
                "markout_5s": s.markout_5s,
            }
        )
    declines_json = [
        {"t_us": d.t_us, "trader": d.trader, "side_intent": d.side_intent, "reason": d.reason}
        for d in result.declines
    ]
    return {
        "fills": fills_json,
        "declines": declines_json,
        "v_terminal": result.v_terminal,
        "inventory_terminal": result.inventory,
        "cash_terminal": result.cash,
        "pnl_decomposition_half_ticks": decomp.to_json(),
    }


def make_vector(
    name: str,
    description: str,
    params: SimParams,
    seed: int,
    quote_schedule: list[tuple[int, int, int]],
    condition=None,
    max_tries: int = 4000,
) -> dict:
    """Assemble a certified vector, re-rolling the seed deterministically
    (seed, seed+SEED_RETRY_STEP, ...) until certification and the optional
    ``condition(result)`` predicate both pass. meta.seed records the final
    seed actually used (provenance only, §6.2)."""
    from .events import event_to_json

    s = seed
    for _ in range(max_tries):
        try:
            events = generate_stream(params, s, quote_schedule)
            certify(params, events)
        except CertificationError:
            s += SEED_RETRY_STEP
            continue
        if condition is not None:
            result = run_stream(params, events)
            if not condition(result):
                s += SEED_RETRY_STEP
                continue
        return {
            "meta": {
                "schema_version": 1,
                "name": name,
                "description": description,
                "seed": s,
                "params": params.to_meta(),
            },
            "event_stream": [event_to_json(ev) for ev in events],
            "expected_output": expected_output(params, events),
        }
    raise CertificationError(f"no qualifying seed found for vector {name!r} after {max_tries} tries")


def vector_from_events(name: str, description: str, params: SimParams, seed: int, events: list) -> dict:
    """Hand-authored vector from an explicit event list (still certified)."""
    from .events import event_to_json

    certify(params, events)
    return {
        "meta": {
            "schema_version": 1,
            "name": name,
            "description": description,
            "seed": seed,
            "params": params.to_meta(),
        },
        "event_stream": [event_to_json(ev) for ev in events],
        "expected_output": expected_output(params, events),
    }


# The parameter set the frozen vectors were generated under (the v1.0 §1.5
# defaults). Pinned explicitly so re-running build_inventory reproduces the
# frozen artifacts even after SimParams defaults move to the final gate
# regime. Vectors embed their own params, so this never affects conformance.
_VECTOR_PARAMS = SimParams(
    v0=10_000, round_us=60_000_000, lambda_j=0.5, p_jump=0.2,
    lambda_a=4.0, alpha=0.3, delta0=4.0,
)


def _hand_verified_vector() -> dict:
    """The hand-verified §6.4 vector. Full arithmetic in tests/test_vectors.py.

    Stream: quote (9995,10005) @0; informed @250003 declines (V=10000 inside);
    jump +9 @1100009; informed @1400011 buys at 10005 (V=10009); quote
    (10004,10010) @2000003; noise sell u=0.30 @2600017 fills at 10004
    (f=exp(-0.75)~0.4724 > 0.30); jump -4 @4100023; noise buy u=0.62
    @5200031 balks (0.62 > f). Expected (half-ticks): SC=16, AS=-14, IC=0,
    total=2 == 2*(cash=1 + inv=0 * V_T=10005).
    """
    from .events import ArrivalEvent, JumpEvent, QuoteEvent

    params = _VECTOR_PARAMS
    events = [
        QuoteEvent(0, 9995, 10005),
        ArrivalEvent(250_003, "informed", None, None),
        JumpEvent(1_100_009, 9),
        ArrivalEvent(1_400_011, "informed", None, None),
        QuoteEvent(2_000_003, 10004, 10010),
        ArrivalEvent(2_600_017, "noise", "sell", 0.30),
        JumpEvent(4_100_023, -4),
        ArrivalEvent(5_200_031, "noise", "buy", 0.62),
    ]
    doc = vector_from_events(
        "hand_verified_mixed",
        "Hand-verified: informed decline, informed pick-off, quote move, noise fill, "
        "noise balk; SC=16 AS=-14 IC=0 total=2 half-ticks (arithmetic in test_vectors.py).",
        params,
        0,
        events,
    )
    # Defense in depth: the engine must agree with the hand arithmetic.
    assert doc["expected_output"]["pnl_decomposition_half_ticks"] == {
        "total": 2, "spread_captured": 16, "adverse_selection": -14, "inventory_cost": 0,
    }, doc["expected_output"]["pnl_decomposition_half_ticks"]
    return doc


def build_inventory(out_dir) -> list[str]:
    """Generate and write the full §6.4 vector inventory (the smoke vector is
    hand-frozen separately, byte-identical to DESIGN.md §6.2). Returns the
    vector names written."""
    from pathlib import Path

    from .vectors import save_vector

    out = Path(out_dir)
    P = _VECTOR_PARAMS
    v0 = P.v0
    static3 = [(0, v0 - 3, v0 + 3)]
    static5 = [(0, v0 - 5, v0 + 5)]
    wide = [(0, v0 - 150, v0 + 150)]
    stepping = [
        (0, 9997, 10003), (7_000_003, 9999, 10005), (14_000_007, 9995, 10001),
        (21_000_011, 10001, 10007), (28_000_013, 9996, 10004), (35_000_017, 10000, 10006),
        (42_000_019, 9994, 10000), (49_000_023, 9998, 10006), (56_000_027, 9997, 10003),
    ]
    kitchen = [
        (0, 9996, 10004), (5_000_003, 9998, 10001), (11_000_007, 9990, 10010),
        (18_000_011, 10002, 10003), (26_000_013, 9995, 10009), (33_000_017, 9999, 10000),
        (41_000_019, 9985, 10015), (50_000_023, 9997, 10002), (57_000_027, 9994, 10006),
    ]

    def max_abs_inv(result):
        inv = peak = 0
        for f in result.fills:
            inv += f.q
            peak = max(peak, abs(inv))
        return peak

    docs = [
        _hand_verified_vector(),
        vector_from_events(
            "empty_round",
            "No arrivals, no jumps: the identity holds at all-zeros.",
            P, 0, [QuoteEvent(0, v0 - 3, v0 + 3)],
        ),
        make_vector("noise_only", "alpha=0: pure noise flow, tight quotes.",
                    SimParams(alpha=0.0, lambda_j=P.lambda_j, delta0=P.delta0), 1001, static3,
                    condition=lambda r: len(r.fills) >= 5),
        make_vector("informed_only", "alpha=1: pure informed flow; fills and declines.",
                    SimParams(alpha=1.0, lambda_j=P.lambda_j, delta0=P.delta0), 1002, static3,
                    condition=lambda r: len(r.fills) >= 1 and len(r.declines) >= 1),
        make_vector("jump_heavy", "lambda_j=3.0: many jumps between fills.",
                    SimParams(lambda_j=3.0, alpha=P.alpha, delta0=P.delta0), 1003, static5,
                    condition=lambda r: len(r.jumps) >= 5),
        make_vector("declines_only", "Very wide quotes: every arrival declines.",
                    SimParams(lambda_j=0.2, alpha=P.alpha, delta0=P.delta0), 1004, wide,
                    condition=lambda r: not r.fills and len(r.declines) >= 10),
        make_vector("quote_changes_mid_round", "Scripted quote schedule stepping through the round.",
                    P, 1005, stepping,
                    condition=lambda r: len(r.fills) >= 5),
        make_vector("markout_clamp", "A fill inside the last second: both markouts clamp at T.",
                    P, 1006, static3,
                    condition=lambda r: any(f.t_us >= P.round_us - 1_000_000 for f in r.fills)),
        make_vector("negative_inventory", "Round ends short (inventory <= -3).",
                    P, 1007, static3,
                    condition=lambda r: r.inventory <= -3),
        make_vector("long_round_trip", "Inventory swings (peak |inv| >= 2) but ends flat.",
                    P, 1008, static3,
                    condition=lambda r: r.inventory == 0 and len(r.fills) >= 8 and max_abs_inv(r) >= 2),
        make_vector("kitchen_sink", "Default params, busy schedule: fills, declines, jumps galore.",
                    P, 1009, kitchen,
                    condition=lambda r: len(r.fills) >= 20 and len(r.declines) >= 10 and len(r.jumps) >= 10),
    ]
    names = []
    for doc in docs:
        save_vector(doc, out / f"{doc['meta']['name']}.json")
        names.append(doc["meta"]["name"])
    return names


def next_good_seed(params: SimParams, seed: int, max_tries: int = 1000) -> int:
    """First seed >= the given one whose harness stream (no quotes) passes the
    V>0 path check — used by the gate runner so every paired run gets a valid
    common-random-numbers stream."""
    s = seed
    for _ in range(max_tries):
        try:
            generate_stream(params, s, None)
            return s
        except CertificationError:
            s += SEED_RETRY_STEP
    raise CertificationError(f"no V>0 stream found near seed {seed}")
