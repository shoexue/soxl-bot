import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSignalRows,
  easternLocalToUtcIso,
  isMarketRefreshWindow,
  normalizeTwelveDataTimestamp,
  parseTwelveDataBars,
} from "../src/strategy.js";

function bar(symbol, localDatetime, open, close, volume = 1_000_000) {
  return {
    symbol,
    timestamp: easternLocalToUtcIso(localDatetime),
    local_datetime: localDatetime,
    market_date: localDatetime.slice(0, 10),
    interval: "30min",
    open,
    high: Math.max(open, close) + 0.5,
    low: Math.min(open, close) - 0.5,
    close,
    volume,
  };
}

test("normalizes Twelve Data timestamps missing the date/time separator", () => {
  assert.equal(
    normalizeTwelveDataTimestamp("2026-07-3013:00:00"),
    "2026-07-30T13:00:00",
  );
  assert.equal(
    easternLocalToUtcIso("2026-07-30 15:30:00"),
    "2026-07-30T19:30:00.000Z",
  );
});

test("drops an incomplete current 30-minute bar", () => {
  const values = [
    {
      datetime: "2026-07-30 10:00:00",
      open: "100",
      high: "101",
      low: "99",
      close: "100.5",
      volume: "1000",
    },
    {
      datetime: "2026-07-30 09:30:00",
      open: "99",
      high: "100",
      low: "98",
      close: "99.5",
      volume: "900",
    },
  ];

  const rows = parseTwelveDataBars(
    values,
    "SOXL",
    new Date("2026-07-30T14:01:00Z"),
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].local_datetime, "2026-07-30T09:30:00");
});

test("runs scheduled API calls only during the Eastern market window", () => {
  assert.equal(
    isMarketRefreshWindow(new Date("2026-07-30T14:01:00Z")),
    true,
  );
  assert.equal(
    isMarketRefreshWindow(new Date("2026-07-30T20:01:00Z")),
    true,
  );
  assert.equal(
    isMarketRefreshWindow(new Date("2026-07-30T20:31:00Z")),
    false,
  );
  assert.equal(
    isMarketRefreshWindow(new Date("2026-08-01T14:01:00Z")),
    false,
  );
});

test("matches the validated v4 oversold-then-bounce behavior", () => {
  const times = ["09:30", "10:00", "10:30", "11:00", "11:30", "12:00"];
  const opens = [100, 100, 101, 102, 101, 95];
  const closes = [100, 101, 102, 101, 95, 97];
  const soxl = times.map((time, index) =>
    bar(
      "SOXL",
      `2026-07-08T${time}:00`,
      opens[index],
      closes[index],
    ),
  );
  const qqq = times.map((time) =>
    bar("QQQ", `2026-07-08T${time}:00`, 500, 500),
  );

  const rows = buildSignalRows(
    soxl,
    qqq,
    new Date("2026-07-08T17:00:00Z"),
  );
  assert.equal(rows.at(-2).episode_start_30m, true);
  assert.equal(rows.at(-2).shadow_action, "OVERSOLD_WATCH");
  assert.equal(rows.at(-1).bounce_confirmed_30m, true);
  assert.equal(rows.at(-1).shadow_signal, true);
  assert.equal(rows.at(-1).shadow_action, "SHADOW_LONG_WATCH");
  assert.equal(rows.at(-1).bars_since_episode_start_30m, 1);
});

test("blocks the bounce when QQQ is below the intraday floor", () => {
  const times = ["09:30", "10:00", "10:30", "11:00", "11:30", "12:00"];
  const opens = [100, 100, 101, 102, 101, 95];
  const closes = [100, 101, 102, 101, 95, 97];
  const soxl = times.map((time, index) =>
    bar(
      "SOXL",
      `2026-07-08T${time}:00`,
      opens[index],
      closes[index],
    ),
  );
  const qqq = times.map((time, index) =>
    bar(
      "QQQ",
      `2026-07-08T${time}:00`,
      500,
      index === times.length - 1 ? 494 : 500,
    ),
  );

  const rows = buildSignalRows(soxl, qqq);
  assert.equal(rows.at(-1).bounce_confirmed_30m, true);
  assert.equal(rows.at(-1).regime_ok_30m, false);
  assert.equal(rows.at(-1).shadow_signal, false);
  assert.equal(rows.at(-1).shadow_action, "REGIME_BLOCKED");
});
