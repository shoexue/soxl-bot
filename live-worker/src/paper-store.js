import {
  PAPER_ACCOUNT_ID,
  PAPER_CONFIG,
  defaultPaperState,
  normalizePaperState,
  processPaperBar,
} from "./paper.js";

const STATE_COLUMNS = [
  "strategy_version",
  "starting_capital",
  "paper_equity",
  "cash",
  "marked_equity",
  "in_position",
  "pending_entry",
  "pending_signal_timestamp",
  "pending_market_date",
  "pending_entry_z",
  "entry_signal_timestamp",
  "entry_timestamp",
  "entry_price",
  "entry_z",
  "shares",
  "invested_capital",
  "equity_before_entry",
  "bars_held",
  "position_market_value",
  "current_position_return",
  "last_processed_timestamp",
  "last_action",
  "last_reason",
  "equity_peak",
  "max_drawdown",
  "activated_at",
  "updated_at",
];

function databaseValue(value) {
  if (typeof value === "boolean") return Number(value);
  return value ?? null;
}

function normalizedDecision(row) {
  if (!row) return null;
  return {
    ...row,
    shadow_signal: Boolean(row.shadow_signal),
    pending_entry: Boolean(row.pending_entry),
    in_position: Boolean(row.in_position),
  };
}

function normalizedEquity(row) {
  if (!row) return null;
  return {
    ...row,
    pending_entry: Boolean(row.pending_entry),
    in_position: Boolean(row.in_position),
  };
}

function stateInsertStatement(db, state) {
  const columns = ["account_id", ...STATE_COLUMNS];
  const placeholders = columns.map(() => "?").join(", ");
  return db
    .prepare(
      `INSERT INTO paper_accounts (${columns.join(", ")})
       VALUES (${placeholders})`,
    )
    .bind(...columns.map((column) => databaseValue(state[column])));
}

function stateUpdateStatement(db, state) {
  const assignments = STATE_COLUMNS.map((column) => `${column} = ?`).join(", ");
  return db
    .prepare(
      `UPDATE paper_accounts SET ${assignments} WHERE account_id = ?`,
    )
    .bind(
      ...STATE_COLUMNS.map((column) => databaseValue(state[column])),
      state.account_id,
    );
}

function decisionStatement(db, decision) {
  return db
    .prepare(
      `INSERT INTO paper_decisions (
        account_id, timestamp, processed_at, market_date, strategy_version,
        action, reason, shadow_signal, shadow_action, soxl_open, soxl_close,
        soxl_z_5bar, qqq_from_open_pct, account_state, pending_entry,
        in_position, entry_timestamp, entry_price, shares, bars_held,
        paper_cash, paper_realized_equity, paper_marked_equity,
        current_position_return
      ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
      )
      ON CONFLICT(account_id, timestamp) DO NOTHING`,
    )
    .bind(
      decision.account_id,
      decision.timestamp,
      decision.processed_at,
      decision.market_date,
      decision.strategy_version,
      decision.action,
      decision.reason,
      Number(decision.shadow_signal),
      decision.shadow_action,
      decision.soxl_open,
      decision.soxl_close,
      decision.soxl_z_5bar,
      decision.qqq_from_open_pct,
      decision.account_state,
      Number(decision.pending_entry),
      Number(decision.in_position),
      decision.entry_timestamp,
      decision.entry_price,
      decision.shares,
      decision.bars_held,
      decision.paper_cash,
      decision.paper_realized_equity,
      decision.paper_marked_equity,
      decision.current_position_return,
    );
}

function tradeStatement(db, trade) {
  return db
    .prepare(
      `INSERT INTO paper_trades (
        trade_id, account_id, strategy_version, entry_signal_timestamp,
        entry_timestamp, exit_timestamp, entry_price, exit_price, shares,
        bars_held, position_return, account_return, realized_pnl,
        equity_before_entry, equity_after_exit, entry_z, exit_reason, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(trade_id) DO NOTHING`,
    )
    .bind(
      trade.trade_id,
      trade.account_id,
      trade.strategy_version,
      trade.entry_signal_timestamp,
      trade.entry_timestamp,
      trade.exit_timestamp,
      trade.entry_price,
      trade.exit_price,
      trade.shares,
      trade.bars_held,
      trade.position_return,
      trade.account_return,
      trade.realized_pnl,
      trade.equity_before_entry,
      trade.equity_after_exit,
      trade.entry_z,
      trade.exit_reason,
      trade.created_at,
    );
}

function equityStatement(db, equity) {
  return db
    .prepare(
      `INSERT INTO paper_equity (
        account_id, timestamp, market_date, marked_equity, realized_equity,
        cash, in_position, pending_entry, drawdown
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(account_id, timestamp) DO UPDATE SET
        marked_equity = excluded.marked_equity,
        realized_equity = excluded.realized_equity,
        cash = excluded.cash,
        in_position = excluded.in_position,
        pending_entry = excluded.pending_entry,
        drawdown = excluded.drawdown`,
    )
    .bind(
      equity.account_id,
      equity.timestamp,
      equity.market_date,
      equity.marked_equity,
      equity.realized_equity,
      equity.cash,
      Number(equity.in_position),
      Number(equity.pending_entry),
      equity.drawdown,
    );
}

export async function activatePaperAccount(db, now = new Date()) {
  const existing = await db
    .prepare(`SELECT * FROM paper_accounts WHERE account_id = ?`)
    .bind(PAPER_ACCOUNT_ID)
    .first();
  if (existing) {
    return { activated: false, state: normalizePaperState(existing) };
  }

  const latest = await db
    .prepare(
      `SELECT timestamp, market_date, soxl_close, soxl_z_5bar,
              qqq_from_open_pct, shadow_action
       FROM signal_bars
       ORDER BY timestamp DESC
       LIMIT 1`,
    )
    .first();
  const activatedAt = now.toISOString();
  const state = defaultPaperState(latest?.timestamp ?? null, activatedAt);
  const activationTimestamp = latest?.timestamp ?? activatedAt;
  const marketDate = latest?.market_date ?? activatedAt.slice(0, 10);
  const decision = {
    account_id: state.account_id,
    timestamp: activationTimestamp,
    processed_at: activatedAt,
    market_date: marketDate,
    strategy_version: state.strategy_version,
    action: "ACTIVATED",
    reason: state.last_reason,
    shadow_signal: false,
    shadow_action: latest?.shadow_action ?? null,
    soxl_open: null,
    soxl_close: latest?.soxl_close ?? null,
    soxl_z_5bar: latest?.soxl_z_5bar ?? null,
    qqq_from_open_pct: latest?.qqq_from_open_pct ?? null,
    account_state: "flat",
    pending_entry: false,
    in_position: false,
    entry_timestamp: null,
    entry_price: null,
    shares: 0,
    bars_held: 0,
    paper_cash: state.cash,
    paper_realized_equity: state.paper_equity,
    paper_marked_equity: state.marked_equity,
    current_position_return: 0,
  };
  const equity = {
    account_id: state.account_id,
    timestamp: activationTimestamp,
    market_date: marketDate,
    marked_equity: state.marked_equity,
    realized_equity: state.paper_equity,
    cash: state.cash,
    in_position: false,
    pending_entry: false,
    drawdown: 0,
  };
  await db.batch([
    stateInsertStatement(db, state),
    decisionStatement(db, decision),
    equityStatement(db, equity),
  ]);
  return { activated: true, state };
}

export async function processNewPaperBars(db, now = new Date()) {
  const stored = await db
    .prepare(`SELECT * FROM paper_accounts WHERE account_id = ?`)
    .bind(PAPER_ACCOUNT_ID)
    .first();
  if (!stored) {
    return { active: false, processed_bars: 0 };
  }

  let state = normalizePaperState(stored);
  if (!state.last_processed_timestamp) {
    const latest = await db
      .prepare(`SELECT timestamp FROM signal_bars ORDER BY timestamp DESC LIMIT 1`)
      .first();
    if (latest?.timestamp) {
      state.last_processed_timestamp = latest.timestamp;
      state.updated_at = now.toISOString();
      await stateUpdateStatement(db, state).run();
    }
    return { active: true, processed_bars: 0, state };
  }

  const result = await db
    .prepare(
      `SELECT * FROM signal_bars
       WHERE timestamp > ?
       ORDER BY timestamp ASC`,
    )
    .bind(state.last_processed_timestamp)
    .all();
  const statements = [];
  const trades = [];
  let processedBars = 0;

  for (const rawBar of result.results) {
    const bar = {
      ...rawBar,
      shadow_signal: Boolean(rawBar.shadow_signal),
    };
    const processed = processPaperBar(state, bar, now);
    if (!processed.processed) continue;
    state = processed.state;
    processedBars += 1;
    statements.push(decisionStatement(db, processed.decision));
    statements.push(equityStatement(db, processed.equity));
    if (processed.trade) {
      trades.push(processed.trade);
      statements.push(tradeStatement(db, processed.trade));
    }
  }

  if (processedBars) {
    statements.push(stateUpdateStatement(db, state));
    for (let index = 0; index < statements.length; index += 50) {
      await db.batch(statements.slice(index, index + 50));
    }
  }
  return {
    active: true,
    processed_bars: processedBars,
    trades_closed: trades.length,
    state,
  };
}

export async function paperDashboardPayload(db) {
  const stateResult = await db
    .prepare(`SELECT * FROM paper_accounts WHERE account_id = ?`)
    .bind(PAPER_ACCOUNT_ID)
    .first();
  if (!stateResult) {
    return {
      active: false,
      disclosure: "The forward-only cloud paper account has not been activated.",
      state: null,
      summary: null,
      decisions: [],
      trades: [],
      equity_curve: [],
    };
  }

  const [decisionsResult, tradesResult, equityResult, stats] =
    await Promise.all([
      db
        .prepare(
          `SELECT * FROM paper_decisions
           WHERE account_id = ?
           ORDER BY timestamp DESC
           LIMIT 40`,
        )
        .bind(PAPER_ACCOUNT_ID)
        .all(),
      db
        .prepare(
          `SELECT * FROM paper_trades
           WHERE account_id = ?
           ORDER BY exit_timestamp DESC
           LIMIT 40`,
        )
        .bind(PAPER_ACCOUNT_ID)
        .all(),
      db
        .prepare(
          `SELECT * FROM paper_equity
           WHERE account_id = ?
           ORDER BY timestamp DESC
           LIMIT 120`,
        )
        .bind(PAPER_ACCOUNT_ID)
        .all(),
      db
        .prepare(
          `SELECT
             COUNT(*) AS closed_trades,
             SUM(CASE WHEN position_return > 0 THEN 1 ELSE 0 END) AS wins,
             AVG(position_return) AS avg_position_return,
             AVG(account_return) AS avg_account_return,
             MAX(position_return) AS best_trade,
             MIN(position_return) AS worst_trade,
             SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END)
               AS gross_profit,
             ABS(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END))
               AS gross_loss
           FROM paper_trades
           WHERE account_id = ?`,
        )
        .bind(PAPER_ACCOUNT_ID)
        .first(),
    ]);

  const state = normalizePaperState(stateResult);
  const closedTrades = Number(stats?.closed_trades || 0);
  const grossLoss = Number(stats?.gross_loss || 0);
  const summary = {
    active: true,
    strategy_version: state.strategy_version,
    activated_at: state.activated_at,
    starting_capital: state.starting_capital,
    marked_equity: state.marked_equity,
    realized_equity: state.paper_equity,
    cash: state.cash,
    total_return: state.marked_equity / state.starting_capital - 1,
    realized_return: state.paper_equity / state.starting_capital - 1,
    realized_pnl: state.paper_equity - state.starting_capital,
    unrealized_pnl: state.marked_equity - state.paper_equity,
    closed_trades: closedTrades,
    wins: Number(stats?.wins || 0),
    win_rate: closedTrades ? Number(stats?.wins || 0) / closedTrades : null,
    avg_position_return: stats?.avg_position_return ?? null,
    avg_account_return: stats?.avg_account_return ?? null,
    best_trade: stats?.best_trade ?? null,
    worst_trade: stats?.worst_trade ?? null,
    gross_profit: Number(stats?.gross_profit || 0),
    gross_loss: grossLoss,
    profit_factor:
      grossLoss > 0 ? Number(stats?.gross_profit || 0) / grossLoss : null,
    max_drawdown: state.max_drawdown,
    in_position: state.in_position,
    pending_entry: state.pending_entry,
    current_position_return: state.current_position_return,
    position_market_value: state.position_market_value,
    exposure:
      state.marked_equity > 0
        ? state.position_market_value / state.marked_equity
        : 0,
    entry_execution: PAPER_CONFIG.entryExecution,
    position_fraction: PAPER_CONFIG.positionFraction,
    slippage: PAPER_CONFIG.slippage,
    hold_bars: PAPER_CONFIG.holdBars,
    allow_overnight: PAPER_CONFIG.allowOvernight,
    last_action: state.last_action,
    last_reason: state.last_reason,
    last_processed_timestamp: state.last_processed_timestamp,
  };

  return {
    active: true,
    disclosure:
      "Forward-only paper trading. No brokerage orders are placed and historical signals do not alter this account.",
    state,
    summary,
    decisions: [...decisionsResult.results].reverse().map(normalizedDecision),
    trades: [...tradesResult.results].reverse(),
    equity_curve: [...equityResult.results].reverse().map(normalizedEquity),
  };
}
