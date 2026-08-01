import {
  STRATEGY,
  buildSignalRows,
  isMarketRefreshWindow,
  parseTwelveDataBars,
} from "./strategy.js";
import {
  activatePaperAccount,
  paperDashboardPayload,
  processNewPaperBars,
} from "./paper-store.js";

const MARKET_SYMBOLS = ["SOXL", "QQQ"];
const BOOLEAN_COLUMNS = [
  "oversold_30m",
  "episode_start_30m",
  "bounce_confirmed_30m",
  "regime_ok_30m",
  "entry_window_ok_30m",
  "shadow_signal",
];

function corsHeaders(request, env) {
  const configured = env.ALLOWED_ORIGIN || "*";
  const requestOrigin = request.headers.get("Origin");
  const allowedOrigin =
    configured === "*" || configured === requestOrigin ? configured : "null";
  return {
    "Access-Control-Allow-Origin": allowedOrigin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Admin-Key",
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    Vary: "Origin",
  };
}

function jsonResponse(request, env, value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: corsHeaders(request, env),
  });
}

function safeMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

async function fetchTwelveDataSymbol(symbol, apiKey, now) {
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("interval", "30min");
  url.searchParams.set("outputsize", "60");
  url.searchParams.set("timezone", "America/New_York");

  const response = await fetch(url, {
    headers: { Authorization: `apikey ${apiKey}` },
  });
  if (!response.ok) {
    throw new Error(`Twelve Data ${symbol} request returned ${response.status}`);
  }
  const payload = await response.json();
  if (payload.status === "error") {
    throw new Error(
      `Twelve Data ${symbol}: ${payload.message || "unknown API error"}`,
    );
  }
  return parseTwelveDataBars(payload.values, symbol, now);
}

async function batchStatements(db, statements, chunkSize = 50) {
  for (let index = 0; index < statements.length; index += chunkSize) {
    await db.batch(statements.slice(index, index + chunkSize));
  }
}

async function upsertMarketBars(db, bars, fetchedAt) {
  const statements = bars.map((bar) =>
    db
      .prepare(
        `INSERT INTO market_bars (
          symbol, timestamp, local_datetime, market_date, interval,
          open, high, low, close, volume, source, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'twelve_data', ?)
        ON CONFLICT(symbol, timestamp) DO UPDATE SET
          local_datetime = excluded.local_datetime,
          market_date = excluded.market_date,
          open = excluded.open,
          high = excluded.high,
          low = excluded.low,
          close = excluded.close,
          volume = excluded.volume,
          fetched_at = excluded.fetched_at`,
      )
      .bind(
        bar.symbol,
        bar.timestamp,
        bar.local_datetime,
        bar.market_date,
        bar.interval,
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.volume,
        fetchedAt,
      ),
  );
  await batchStatements(db, statements);
}

async function loadRecentMarketBars(db, symbol, limit = 160) {
  const result = await db
    .prepare(
      `SELECT symbol, timestamp, local_datetime, market_date, interval,
              open, high, low, close, volume
       FROM market_bars
       WHERE symbol = ?
       ORDER BY timestamp DESC
       LIMIT ?`,
    )
    .bind(symbol, limit)
    .all();
  return [...result.results].reverse();
}

async function upsertSignalRows(db, rows) {
  const statements = rows.map((row) =>
    db
      .prepare(
        `INSERT INTO signal_bars (
          timestamp, local_datetime, market_date, interval, strategy_version,
          soxl_open, soxl_high, soxl_low, soxl_close, soxl_volume, soxl_vwap,
          soxl_return_30m_pct, soxl_z_5bar, soxl_vs_vwap_pct,
          soxl_from_open_pct, soxl_from_high_pct, soxl_from_low_pct,
          soxl_session_range_pct, soxl_session_high, soxl_session_low,
          bar_number, qqq_close, qqq_return_30m_pct, qqq_from_open_pct,
          bars_in_window, oversold_30m, episode_start_30m,
          bars_since_episode_start_30m, bounce_confirmed_30m, regime_ok_30m,
          entry_window_ok_30m, shadow_signal, shadow_action, shadow_reason,
          calculated_at
        ) VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(timestamp) DO UPDATE SET
          local_datetime = excluded.local_datetime,
          market_date = excluded.market_date,
          strategy_version = excluded.strategy_version,
          soxl_open = excluded.soxl_open,
          soxl_high = excluded.soxl_high,
          soxl_low = excluded.soxl_low,
          soxl_close = excluded.soxl_close,
          soxl_volume = excluded.soxl_volume,
          soxl_vwap = excluded.soxl_vwap,
          soxl_return_30m_pct = excluded.soxl_return_30m_pct,
          soxl_z_5bar = excluded.soxl_z_5bar,
          soxl_vs_vwap_pct = excluded.soxl_vs_vwap_pct,
          soxl_from_open_pct = excluded.soxl_from_open_pct,
          soxl_from_high_pct = excluded.soxl_from_high_pct,
          soxl_from_low_pct = excluded.soxl_from_low_pct,
          soxl_session_range_pct = excluded.soxl_session_range_pct,
          soxl_session_high = excluded.soxl_session_high,
          soxl_session_low = excluded.soxl_session_low,
          bar_number = excluded.bar_number,
          qqq_close = excluded.qqq_close,
          qqq_return_30m_pct = excluded.qqq_return_30m_pct,
          qqq_from_open_pct = excluded.qqq_from_open_pct,
          oversold_30m = excluded.oversold_30m,
          episode_start_30m = excluded.episode_start_30m,
          bars_since_episode_start_30m =
            excluded.bars_since_episode_start_30m,
          bounce_confirmed_30m = excluded.bounce_confirmed_30m,
          regime_ok_30m = excluded.regime_ok_30m,
          entry_window_ok_30m = excluded.entry_window_ok_30m,
          shadow_signal = excluded.shadow_signal,
          shadow_action = excluded.shadow_action,
          shadow_reason = excluded.shadow_reason,
          calculated_at = excluded.calculated_at`,
      )
      .bind(
        row.timestamp,
        row.local_datetime,
        row.market_date,
        row.interval,
        row.strategy_version,
        row.soxl_open,
        row.soxl_high,
        row.soxl_low,
        row.soxl_close,
        row.soxl_volume,
        row.soxl_vwap,
        row.soxl_return_30m_pct,
        row.soxl_z_5bar,
        row.soxl_vs_vwap_pct,
        row.soxl_from_open_pct,
        row.soxl_from_high_pct,
        row.soxl_from_low_pct,
        row.soxl_session_range_pct,
        row.soxl_session_high,
        row.soxl_session_low,
        row.bar_number,
        row.qqq_close,
        row.qqq_return_30m_pct,
        row.qqq_from_open_pct,
        row.bars_in_window,
        Number(row.oversold_30m),
        Number(row.episode_start_30m),
        row.bars_since_episode_start_30m,
        Number(row.bounce_confirmed_30m),
        Number(row.regime_ok_30m),
        Number(row.entry_window_ok_30m),
        Number(row.shadow_signal),
        row.shadow_action,
        row.shadow_reason,
        row.calculated_at,
      ),
  );
  await batchStatements(db, statements);
}

async function refreshMarketData(env, now = new Date()) {
  if (!env.TWELVE_DATA_API_KEY) {
    throw new Error("TWELVE_DATA_API_KEY secret is not configured");
  }

  const runId = crypto.randomUUID();
  const startedAt = now.toISOString();
  await env.DB.prepare(
    `INSERT INTO refresh_runs (run_id, started_at, status, message)
     VALUES (?, ?, 'running', '')`,
  )
    .bind(runId, startedAt)
    .run();

  try {
    const [soxlFetched, qqqFetched] = await Promise.all(
      MARKET_SYMBOLS.map((symbol) =>
        fetchTwelveDataSymbol(symbol, env.TWELVE_DATA_API_KEY, now),
      ),
    );
    await upsertMarketBars(env.DB, soxlFetched, startedAt);
    await upsertMarketBars(env.DB, qqqFetched, startedAt);

    const [soxlHistory, qqqHistory] = await Promise.all([
      loadRecentMarketBars(env.DB, "SOXL"),
      loadRecentMarketBars(env.DB, "QQQ"),
    ]);
    const signalRows = buildSignalRows(soxlHistory, qqqHistory, now);
    await upsertSignalRows(env.DB, signalRows);
    const paperResult = await processNewPaperBars(env.DB, now);

    const latest = signalRows.at(-1) || null;
    await env.DB.prepare(
      `UPDATE refresh_runs
       SET completed_at = ?, status = 'ok', message = ?,
           soxl_rows = ?, qqq_rows = ?, aligned_rows = ?,
           latest_bar_timestamp = ?
       WHERE run_id = ?`,
    )
      .bind(
        new Date().toISOString(),
        "Completed SOXL/QQQ refresh.",
        soxlFetched.length,
        qqqFetched.length,
        signalRows.length,
        latest?.timestamp ?? null,
        runId,
      )
      .run();

    return {
      ok: true,
      run_id: runId,
      fetched: { SOXL: soxlFetched.length, QQQ: qqqFetched.length },
      aligned_rows: signalRows.length,
      latest_bar: latest,
      paper: paperResult,
    };
  } catch (error) {
    const message = safeMessage(error);
    await env.DB.prepare(
      `UPDATE refresh_runs
       SET completed_at = ?, status = 'error', message = ?
       WHERE run_id = ?`,
    )
      .bind(new Date().toISOString(), message, runId)
      .run();
    throw error;
  }
}

function normalizeSignalRow(row) {
  if (!row) return null;
  const normalized = { ...row };
  for (const column of BOOLEAN_COLUMNS) {
    normalized[column] = Boolean(normalized[column]);
  }
  return normalized;
}

async function latestRefresh(db) {
  return db
    .prepare(
      `SELECT * FROM refresh_runs
       ORDER BY started_at DESC
       LIMIT 1`,
    )
    .first();
}

async function healthPayload(env) {
  const [refresh, latestBar, counts, paperAccount] = await Promise.all([
    latestRefresh(env.DB),
    env.DB.prepare(
      `SELECT timestamp, local_datetime, market_date, calculated_at
       FROM signal_bars
       ORDER BY timestamp DESC
       LIMIT 1`,
    ).first(),
    env.DB.prepare(
      `SELECT
        (SELECT COUNT(*) FROM market_bars WHERE symbol = 'SOXL') AS soxl_bars,
        (SELECT COUNT(*) FROM market_bars WHERE symbol = 'QQQ') AS qqq_bars,
        (SELECT COUNT(*) FROM signal_bars) AS signal_bars`,
    ).first(),
    env.DB.prepare(
      `SELECT account_id, activated_at, marked_equity, in_position,
              pending_entry, last_action, last_processed_timestamp
       FROM paper_accounts
       LIMIT 1`,
    ).first(),
  ]);
  return {
    ok: refresh?.status !== "error",
    strategy_version: STRATEGY.version,
    source: "twelve_data",
    latest_bar: latestBar,
    latest_refresh: refresh,
    counts: counts || {},
    paper_account: paperAccount
      ? {
          ...paperAccount,
          in_position: Boolean(paperAccount.in_position),
          pending_entry: Boolean(paperAccount.pending_entry),
        }
      : null,
  };
}

async function dashboardPayload(env) {
  const [query, refresh, countResult, paper] = await Promise.all([
    env.DB.prepare(
      `SELECT * FROM signal_bars
       ORDER BY timestamp DESC
       LIMIT 120`,
    ).all(),
    latestRefresh(env.DB),
    env.DB.prepare(`SELECT COUNT(*) AS rows FROM signal_bars`).first(),
    paperDashboardPayload(env.DB),
  ]);
  const bars = [...query.results].reverse().map(normalizeSignalRow);
  const latest = bars.at(-1) || {};
  const signals = bars.filter((row) => row.shadow_signal);
  const signalsToday = signals.filter(
    (row) => row.market_date === latest.market_date,
  );
  const latestSignal = signals.at(-1) || null;
  const dataWarning =
    refresh?.status === "error" ? refresh.message : "";

  const latestSnapshot = latest.timestamp
    ? {
        run_timestamp: latest.calculated_at,
        timestamp: latest.timestamp,
        market_date: latest.market_date,
        interval: "30min",
        watch_state: latest.shadow_action,
        reason: latest.shadow_reason,
        soxl_open: latest.soxl_open,
        soxl_last: latest.soxl_close,
        soxl_session_high: latest.soxl_session_high,
        soxl_session_low: latest.soxl_session_low,
        soxl_vwap: latest.soxl_vwap,
        soxl_from_open_pct: latest.soxl_from_open_pct,
        soxl_from_high_pct: latest.soxl_from_high_pct,
        soxl_from_low_pct: latest.soxl_from_low_pct,
        soxl_range_pct: latest.soxl_session_range_pct,
        soxl_vs_vwap_pct: latest.soxl_vs_vwap_pct,
        qqq_last: latest.qqq_close,
        qqq_from_open_pct: latest.qqq_from_open_pct,
        bars_observed: latest.bar_number,
        data_warning: dataWarning,
      }
    : null;

  const emptyBacktest = {
    summary: null,
    best: null,
    validated: null,
    recent_trades: [],
    equity_curve: [],
    bars: [],
    top_parameters: [],
    validation: [],
    robustness: [],
    daily_shock_context: [],
    daily_shock_latest: null,
    challenger: {
      mode: "research_only_local",
      summary: null,
      validation: null,
      recent_trades: [],
      equity_curve: [],
    },
    files: {},
  };

  return {
    generated_at_utc: new Date().toISOString(),
    state: {},
    latest_daily_log: {},
    recent_daily_log: [],
    recent_trades: [],
    paper_signals: [],
    performance: {},
    market: { prices: [], markers: { signals: [], entries: [], exits: [] } },
    historical: { summary: {}, return_path: [], walk_forward: {} },
    intraday: {
      mode: "cloud_live_30m",
      latest: latestSnapshot,
      bars,
      snapshots: latestSnapshot ? [latestSnapshot] : [],
      overnight_rebound_paper: {
        disclosure: "Overnight paper accounting remains local.",
        state: {},
        summary: {},
        decisions: [],
        trades: [],
        files: {},
      },
      thirty_minute: {
        mode: "shadow_fast_30m_live",
        latest: latest.timestamp ? latest : null,
        latest_signal: latestSignal,
        signal_count: signalsToday.length,
        bars,
        signals,
        paper,
        file: {
          exists: Boolean(latest.timestamp),
          rows: Number(countResult?.rows || 0),
          latest_timestamp: latest.timestamp || null,
        },
        adaptive_challenger: {
          mode: "research_only_local",
          latest: null,
          latest_signal: null,
          signal_count: 0,
          bars: [],
          signals: [],
          file: { exists: false, rows: 0 },
        },
        backtest: emptyBacktest,
      },
      files: {
        bars: { exists: Boolean(latest.timestamp), rows: bars.length },
        snapshots: { exists: Boolean(latestSnapshot), rows: latestSnapshot ? 1 : 0 },
        thirty_minute: {
          exists: Boolean(latest.timestamp),
          rows: Number(countResult?.rows || 0),
        },
        thirty_minute_backtest: { exists: false, rows: 0 },
      },
    },
    data_health: {
      source: "twelve_data",
      latest_refresh: refresh,
      warning: dataWarning,
    },
  };
}

async function handleRequest(request, env) {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(request, env) });
  }

  const url = new URL(request.url);
  try {
    if (request.method === "GET" && url.pathname === "/") {
      return jsonResponse(request, env, {
        name: "SOXL Live 30-Minute API",
        strategy_version: STRATEGY.version,
        health: "/api/health",
        dashboard: "/api/dashboard",
      });
    }
    if (request.method === "GET" && url.pathname === "/api/health") {
      return jsonResponse(request, env, await healthPayload(env));
    }
    if (request.method === "GET" && url.pathname === "/api/dashboard") {
      return jsonResponse(request, env, await dashboardPayload(env));
    }
    if (request.method === "POST" && url.pathname === "/api/refresh") {
      const suppliedKey = request.headers.get("X-Admin-Key");
      if (!env.TWELVE_DATA_API_KEY || suppliedKey !== env.TWELVE_DATA_API_KEY) {
        return jsonResponse(request, env, { error: "Unauthorized" }, 401);
      }
      return jsonResponse(request, env, await refreshMarketData(env));
    }
    if (request.method === "POST" && url.pathname === "/api/paper/activate") {
      const suppliedKey = request.headers.get("X-Admin-Key");
      if (!env.TWELVE_DATA_API_KEY || suppliedKey !== env.TWELVE_DATA_API_KEY) {
        return jsonResponse(request, env, { error: "Unauthorized" }, 401);
      }
      return jsonResponse(request, env, await activatePaperAccount(env.DB));
    }
    return jsonResponse(request, env, { error: "Not found" }, 404);
  } catch (error) {
    return jsonResponse(
      request,
      env,
      { error: safeMessage(error), setup_hint: "Apply D1 migrations and configure the Twelve Data secret." },
      500,
    );
  }
}

export default {
  fetch(request, env) {
    return handleRequest(request, env);
  },

  async scheduled(controller, env, ctx) {
    const scheduledAt = new Date(controller.scheduledTime);
    if (!isMarketRefreshWindow(scheduledAt)) {
      console.log("Skipping refresh outside the regular-session completion window.");
      return;
    }
    ctx.waitUntil(
      refreshMarketData(env, scheduledAt).catch((error) => {
        console.error("Scheduled refresh failed", error);
      }),
    );
  },
};
