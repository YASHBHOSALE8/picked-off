"""Golden-vector conformance (DESIGN.md §6): every vectors/*.json validates
against the schema and reproduces expected_output with exact integer equality.

HAND VERIFICATION of hand_verified_mixed.json (DESIGN.md §6.4 requires one
non-trivial vector checked by hand; q = -1 customer buy / +1 customer sell,
half-tick terms per §2.2: sc = a-b, as = q*(2V - a - b), ic = 2q*(V_T - V)):

  events: quote(9995,10005)@0 | informed@250003 | jump +9 @1100009 |
          informed@1400011 | quote(10004,10010)@2000003 |
          noise sell u=.30 @2600017 | jump -4 @4100023 | noise buy u=.62 @5200031

  V path: 10000 -> 10009 (t=1100009) -> 10005 (t=4100023); V_T = 10005.

  arrival@250003 (informed): V=10000 in [9995,10005] -> DECLINE v_inside_quotes.
  arrival@1400011 (informed): ask 10005 < V 10009 -> FILL buy @10005, q=-1
      sc = 10005-9995 = 10        as = -(2*10009-9995-10005) = -(18) = -18
      ic = 2*(-1)*(10005-10009) = +8
      markout_1s: V(2400011)=10009 -> -(10009-10005) = -4
      markout_5s: V(6400011)=10005 -> -(10005-10005) =  0
  arrival@2600017 (noise sell): h=(10010-10004)/2=3, f=exp(-3/4)=0.47237;
      u=0.30 < f -> FILL sell @10004 (bid), q=+1
      sc = 10010-10004 = 6        as = +(2*10009-10004-10010) = +4
      ic = 2*(+1)*(10005-10009) = -8
      markout_1s: V(3600017)=10009 -> +(10009-10004) = +5
      markout_5s: V(7600017)=10005 -> +(10005-10004) = +1
  arrival@5200031 (noise buy): u=0.62 > f=0.47237 -> DECLINE balked_at_spread.

  totals (half-ticks): SC = 10+6 = 16;  AS = -18+4 = -14;  IC = 8-8 = 0
  cash = +10005 (dealer sold) - 10004 (dealer bought) = 1; inv = -1+1 = 0
  total = 16 - 14 + 0 = 2 == 2*(1 + 0*10005) = 2*PnL  [identity holds]
"""

from pathlib import Path

import pytest

from picked_off.vectors import check_conformance, load_vector, validate_vector

VECTOR_DIR = Path(__file__).resolve().parents[2] / "vectors"
VECTOR_PATHS = sorted(VECTOR_DIR.glob("*.json"))


def test_inventory_size_and_smoke_presence():
    names = {p.stem for p in VECTOR_PATHS}
    assert len(VECTOR_PATHS) >= 10, f"need >= 10 vectors, found {len(VECTOR_PATHS)}"
    assert "smoke_two_arrivals" in names  # the DESIGN.md §6.2 example, frozen verbatim
    assert "hand_verified_mixed" in names


@pytest.mark.parametrize("path", VECTOR_PATHS, ids=lambda p: p.stem)
def test_vector_schema_valid(path):
    validate_vector(load_vector(path))


@pytest.mark.parametrize("path", VECTOR_PATHS, ids=lambda p: p.stem)
def test_vector_conformance_exact(path):
    check_conformance(load_vector(path))


@pytest.mark.parametrize("path", VECTOR_PATHS, ids=lambda p: p.stem)
def test_vector_certified(path):
    """Frozen vectors must satisfy full certification (§6.3): timestamp
    hygiene AND the 1e-9 u_accept margin that protects the TS engine."""
    from picked_off.events import parse_stream
    from picked_off.generator import certify

    doc = load_vector(path)
    params = validate_vector(doc)
    certify(params, parse_stream(doc["event_stream"], params.round_us))


def test_hand_verified_numbers():
    """The docstring arithmetic, asserted field by field."""
    doc = load_vector(VECTOR_DIR / "hand_verified_mixed.json")
    out = doc["expected_output"]
    assert out["pnl_decomposition_half_ticks"] == {
        "total": 2, "spread_captured": 16, "adverse_selection": -14, "inventory_cost": 0,
    }
    assert (out["cash_terminal"], out["inventory_terminal"], out["v_terminal"]) == (1, 0, 10005)
    assert [f["t_us"] for f in out["fills"]] == [1_400_011, 2_600_017]
    f1, f2 = out["fills"]
    assert (f1["side"], f1["price"], f1["v_at_fill"]) == ("buy", 10005, 10009)
    assert (f1["markout_1s"], f1["markout_5s"]) == (-4, 0)
    assert (f2["side"], f2["price"], f2["v_at_fill"]) == ("sell", 10004, 10009)
    assert (f2["markout_1s"], f2["markout_5s"]) == (5, 1)
    assert [d["reason"] for d in out["declines"]] == ["v_inside_quotes", "balked_at_spread"]
