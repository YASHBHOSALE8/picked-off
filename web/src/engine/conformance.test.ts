/**
 * Golden-vector conformance (DESIGN.md §6): the TS engine must reproduce
 * every frozen vectors/*.json expected_output with EXACT integer equality
 * (§6.3-1). This suite passing is the engine-done criterion for step ④.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { parseStream } from "./events";
import { runStream } from "./engine";
import { expectedOutput, scoreRound } from "./scoring";
import { paramsFromMeta } from "./params";

const VECTOR_DIR = resolve(__dirname, "../../../vectors");
const vectorFiles = readdirSync(VECTOR_DIR).filter((f) => f.endsWith(".json")).sort();

it("has the full frozen inventory", () => {
  expect(vectorFiles.length).toBeGreaterThanOrEqual(10);
  expect(vectorFiles).toContain("smoke_two_arrivals.json");
  expect(vectorFiles).toContain("hand_verified_mixed.json");
});

describe.each(vectorFiles)("%s", (file) => {
  const doc = JSON.parse(readFileSync(join(VECTOR_DIR, file), "utf-8"));

  it("reproduces expected_output exactly", () => {
    const params = paramsFromMeta(doc.meta.params);
    const events = parseStream(doc.event_stream, params.round_us);
    const result = runStream(params, events);
    // toEqual is deep structural equality; every numeric field is an
    // integer, so this is the §6.3-1 exact-equality contract.
    expect(expectedOutput(result)).toEqual(doc.expected_output);
  });

  it("holds both §2.2 identities exactly", () => {
    const params = paramsFromMeta(doc.meta.params);
    const events = parseStream(doc.event_stream, params.round_us);
    const result = runStream(params, events);
    const { decomp } = scoreRound(result); // throws on either identity failure
    expect(decomp.total).toBe(2 * (result.cash + result.inventory * result.v_terminal));
    expect(decomp.total).toBe(decomp.spread_captured + decomp.adverse_selection + decomp.inventory_cost);
  });
});
