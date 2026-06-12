/**
 * Live-round stream pool (DESIGN.md §7.3 / D12): pre-generated, certified
 * exogenous streams shipped as static assets. The browser never draws model
 * randomness — picking a pool entry is the only (UI-level) randomness.
 */

import { parseStream, type StreamEvent } from "../engine/events";
import { paramsFromMeta, type SimParams } from "../engine/params";

export interface StreamDoc {
  stream_id: string;
  level: number;
  seed: number;
  params: SimParams;
  events: StreamEvent[]; // jumps + arrivals only; the player provides quotes
}

let indexCache: Record<string, string[]> | null = null;

async function fetchJson(path: string): Promise<unknown> {
  const res = await fetch(`${import.meta.env.BASE_URL}${path}`);
  if (!res.ok) throw new Error(`failed to fetch ${path}: ${res.status}`);
  return res.json();
}

export async function loadIndex(): Promise<Record<string, string[]>> {
  if (!indexCache) {
    indexCache = (await fetchJson("streams/index.json")) as Record<string, string[]>;
  }
  return indexCache;
}

export async function loadStream(streamId: string): Promise<StreamDoc> {
  const raw = (await fetchJson(`streams/${streamId}.json`)) as Record<string, unknown>;
  const params = paramsFromMeta(raw.params as Record<string, unknown>);
  const events = parseStream(raw.event_stream, params.round_us, false);
  return {
    stream_id: raw.stream_id as string,
    level: raw.level as number,
    seed: raw.seed as number,
    params,
    events,
  };
}

/** Uniform random pool pick for a level (UI-level randomness only). */
export async function pickStream(level: number): Promise<StreamDoc> {
  const index = await loadIndex();
  const ids = index[String(level)];
  if (!ids || ids.length === 0) throw new Error(`no streams for level ${level}`);
  const id = ids[Math.floor(Math.random() * ids.length)];
  return loadStream(id);
}
