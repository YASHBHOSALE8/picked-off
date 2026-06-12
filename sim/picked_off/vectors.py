"""Golden-vector I/O, schema validation, and conformance checking
(DESIGN.md §6.2).

No simulation logic of its own and no randomness. The conformance check
re-runs a vector's stream through engine + scoring and demands exact
integer equality with expected_output on every field (§6.3-1).
"""

from __future__ import annotations

import json
from pathlib import Path

from .events import StreamError, parse_stream
from .params import SimParams


class VectorError(ValueError):
    """A vector file violates the schema or fails conformance."""


_META_KEYS = {"schema_version", "name", "description", "seed", "params"}
_OUTPUT_KEYS = {
    "fills",
    "declines",
    "v_terminal",
    "inventory_terminal",
    "cash_terminal",
    "pnl_decomposition_half_ticks",
}
_FILL_KEYS = {"t_us", "side", "price", "v_at_fill", "trader", "markout_1s", "markout_5s"}
_DECLINE_KEYS = {"t_us", "trader", "side_intent", "reason"}
_DECOMP_KEYS = {"total", "spread_captured", "adverse_selection", "inventory_cost"}


def _ints(d: dict, keys: set[str], where: str) -> None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, bool) or not isinstance(v, int):
            raise VectorError(f"{where}.{k} must be an integer, got {v!r}")


def validate_vector(doc: dict) -> SimParams:
    """Schema validation per DESIGN.md §6.2; returns the parsed params."""
    if not isinstance(doc, dict) or set(doc) != {"meta", "event_stream", "expected_output"}:
        raise VectorError("vector must have exactly meta/event_stream/expected_output")
    meta = doc["meta"]
    if not isinstance(meta, dict) or set(meta) != _META_KEYS:
        raise VectorError(f"meta keys must be exactly {sorted(_META_KEYS)}")
    _ints(meta, {"schema_version", "seed"}, "meta")
    if meta["schema_version"] != 1:
        raise VectorError(f"unsupported schema_version {meta['schema_version']!r}")
    if not isinstance(meta["name"], str) or not meta["name"]:
        raise VectorError("meta.name must be a nonempty string")
    if not isinstance(meta["description"], str):
        raise VectorError("meta.description must be a string")
    try:
        params = SimParams.from_meta(meta["params"])
    except ValueError as e:
        raise VectorError(f"bad meta.params: {e}") from e

    try:
        parse_stream(doc["event_stream"], params.round_us, require_opening_quote=True)
    except StreamError as e:
        raise VectorError(f"bad event_stream: {e}") from e

    out = doc["expected_output"]
    if not isinstance(out, dict) or set(out) != _OUTPUT_KEYS:
        raise VectorError(f"expected_output keys must be exactly {sorted(_OUTPUT_KEYS)}")
    _ints(out, {"v_terminal", "inventory_terminal", "cash_terminal"}, "expected_output")
    if not isinstance(out["fills"], list) or not isinstance(out["declines"], list):
        raise VectorError("expected_output.fills and .declines must be arrays")

    for i, f in enumerate(out["fills"]):
        if set(f) != _FILL_KEYS:
            raise VectorError(f"fills[{i}] keys must be exactly {sorted(_FILL_KEYS)}")
        _ints(f, {"t_us", "price", "v_at_fill", "markout_1s", "markout_5s"}, f"fills[{i}]")
        if f["side"] not in ("buy", "sell") or f["trader"] not in ("informed", "noise"):
            raise VectorError(f"fills[{i}] has bad side/trader")

    for i, d in enumerate(out["declines"]):
        if set(d) != _DECLINE_KEYS:
            raise VectorError(f"declines[{i}] keys must be exactly {sorted(_DECLINE_KEYS)}")
        _ints(d, {"t_us"}, f"declines[{i}]")
        if d["trader"] == "informed":
            if d["side_intent"] is not None or d["reason"] != "v_inside_quotes":
                raise VectorError(f"declines[{i}]: informed declines have null side, v_inside_quotes")
        elif d["trader"] == "noise":
            if d["side_intent"] not in ("buy", "sell") or d["reason"] != "balked_at_spread":
                raise VectorError(f"declines[{i}]: noise declines have a side, balked_at_spread")
        else:
            raise VectorError(f"declines[{i}] has bad trader {d['trader']!r}")

    dec = out["pnl_decomposition_half_ticks"]
    if not isinstance(dec, dict) or set(dec) != _DECOMP_KEYS:
        raise VectorError(f"decomposition keys must be exactly {sorted(_DECOMP_KEYS)}")
    _ints(dec, _DECOMP_KEYS, "pnl_decomposition_half_ticks")
    if dec["total"] != dec["spread_captured"] + dec["adverse_selection"] + dec["inventory_cost"]:
        raise VectorError("decomposition does not sum to total (§2.2 identity)")
    if dec["total"] != 2 * (out["cash_terminal"] + out["inventory_terminal"] * out["v_terminal"]):
        raise VectorError("decomposition total != 2 * (cash + inv * V_T) (§2.2 identity)")
    return params


def check_conformance(doc: dict) -> None:
    """Re-run the stream; expected_output must match exactly (§6.3-1)."""
    from .generator import expected_output  # engine+scoring path, no RNG

    params = validate_vector(doc)
    events = parse_stream(doc["event_stream"], params.round_us, require_opening_quote=True)
    actual = expected_output(params, events)
    if actual != doc["expected_output"]:
        for key in sorted(_OUTPUT_KEYS):
            if actual.get(key) != doc["expected_output"].get(key):
                raise VectorError(
                    f"conformance failure on {key!r}:\n  expected: {doc['expected_output'].get(key)}"
                    f"\n  actual:   {actual.get(key)}"
                )
        raise VectorError("conformance failure (unlocatable key)")


def load_vector(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_vector(doc: dict, path: str | Path) -> None:
    validate_vector(doc)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
