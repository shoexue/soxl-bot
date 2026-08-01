import assert from "node:assert/strict";
import test from "node:test";

import {
  PAPER_CONFIG,
  defaultPaperState,
  processPaperBar,
} from "../src/paper.js";

function signalBar(overrides = {}) {
  return {
    timestamp: "2026-07-31T14:00:00.000Z",
    market_date: "2026-07-31",
    bar_number: 2,
    soxl_open: 100,
    soxl_close: 101,
    soxl_z_5bar: -0.8,
    qqq_from_open_pct: 0,
    shadow_signal: true,
    shadow_action: "SHADOW_LONG_WATCH",
    ...overrides,
  };
}

test("activation is forward-only and starts flat with $10,000", () => {
  const state = defaultPaperState("2026-07-30T19:30:00.000Z", "2026-07-30T21:00:00.000Z");
  assert.equal(state.starting_capital, 10_000);
  assert.equal(state.marked_equity, 10_000);
  assert.equal(state.in_position, false);
  assert.equal(state.last_processed_timestamp, "2026-07-30T19:30:00.000Z");
});

test("queues on a signal and buys at the next bar open with slippage", () => {
  const initial = defaultPaperState("2026-07-30T19:30:00.000Z");
  const queued = processPaperBar(initial, signalBar());
  assert.equal(queued.decision.action, "QUEUE_BUY");
  assert.equal(queued.state.pending_entry, true);
  assert.equal(queued.state.in_position, false);

  const entered = processPaperBar(
    queued.state,
    signalBar({
      timestamp: "2026-07-31T14:30:00.000Z",
      bar_number: 3,
      soxl_open: 102,
      soxl_close: 103,
      shadow_signal: false,
      shadow_action: "WAIT",
    }),
  );
  assert.equal(entered.decision.action, "BUY");
  assert.equal(entered.state.in_position, true);
  assert.equal(entered.state.pending_entry, false);
  assert.equal(entered.state.invested_capital, 5_000);
  assert.equal(
    entered.state.entry_price,
    102 * (1 + PAPER_CONFIG.slippage),
  );
});

test("exits after three future bars and records performance", () => {
  let state = defaultPaperState("2026-07-30T19:30:00.000Z");
  state = processPaperBar(state, signalBar()).state;
  state = processPaperBar(
    state,
    signalBar({
      timestamp: "2026-07-31T14:30:00.000Z",
      bar_number: 3,
      soxl_open: 100,
      soxl_close: 101,
      shadow_signal: false,
    }),
  ).state;

  for (let index = 1; index <= 2; index += 1) {
    const result = processPaperBar(
      state,
      signalBar({
        timestamp: `2026-07-31T${14 + index}:00:00.000Z`,
        bar_number: 3 + index,
        soxl_open: 101 + index,
        soxl_close: 102 + index,
        shadow_signal: false,
      }),
    );
    state = result.state;
    assert.equal(result.trade, null);
  }

  const exited = processPaperBar(
    state,
    signalBar({
      timestamp: "2026-07-31T17:00:00.000Z",
      bar_number: 6,
      soxl_open: 104,
      soxl_close: 105,
      shadow_signal: false,
    }),
  );
  assert.equal(exited.decision.action, "SELL");
  assert.equal(exited.state.in_position, false);
  assert.equal(exited.trade.bars_held, 3);
  assert.ok(exited.trade.position_return > 0);
  assert.ok(exited.state.paper_equity > 10_000);
});

test("does not queue a next-open trade too late in the session", () => {
  const state = defaultPaperState("2026-07-30T19:30:00.000Z");
  const result = processPaperBar(
    state,
    signalBar({ bar_number: 10 }),
  );
  assert.equal(result.state.pending_entry, false);
  assert.equal(result.decision.action, "SIGNAL_SKIPPED_TOO_LATE");
});
