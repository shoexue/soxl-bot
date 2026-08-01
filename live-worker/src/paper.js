import { STRATEGY } from "./strategy.js";

export const PAPER_ACCOUNT_ID = "fast_30m_live_v1";

export const PAPER_CONFIG = Object.freeze({
  startingCapital: 10_000,
  positionFraction: 0.5,
  slippage: 0.001,
  holdBars: STRATEGY.holdBars,
  entryExecution: "next_bar_open",
  allowOvernight: false,
});

export function defaultPaperState(
  lastProcessedTimestamp = null,
  activatedAt = new Date().toISOString(),
) {
  return {
    account_id: PAPER_ACCOUNT_ID,
    strategy_version: STRATEGY.version,
    starting_capital: PAPER_CONFIG.startingCapital,
    paper_equity: PAPER_CONFIG.startingCapital,
    cash: PAPER_CONFIG.startingCapital,
    marked_equity: PAPER_CONFIG.startingCapital,
    in_position: false,
    pending_entry: false,
    pending_signal_timestamp: null,
    pending_market_date: null,
    pending_entry_z: null,
    entry_signal_timestamp: null,
    entry_timestamp: null,
    entry_price: null,
    entry_z: null,
    shares: 0,
    invested_capital: 0,
    equity_before_entry: null,
    bars_held: 0,
    position_market_value: 0,
    current_position_return: 0,
    last_processed_timestamp: lastProcessedTimestamp,
    last_action: "ACTIVATED",
    last_reason: "Forward-only $10,000 paper account activated.",
    equity_peak: PAPER_CONFIG.startingCapital,
    max_drawdown: 0,
    activated_at: activatedAt,
    updated_at: activatedAt,
  };
}

function accountStateLabel(state) {
  if (state.in_position) return "in_position";
  if (state.pending_entry) return "pending_entry";
  return "flat";
}

function clearPending(state) {
  state.pending_entry = false;
  state.pending_signal_timestamp = null;
  state.pending_market_date = null;
  state.pending_entry_z = null;
}

function clearPosition(state) {
  state.in_position = false;
  state.entry_signal_timestamp = null;
  state.entry_timestamp = null;
  state.entry_price = null;
  state.entry_z = null;
  state.shares = 0;
  state.invested_capital = 0;
  state.equity_before_entry = null;
  state.bars_held = 0;
  state.position_market_value = 0;
  state.current_position_return = 0;
}

function updateDrawdown(state) {
  state.equity_peak = Math.max(
    Number(state.equity_peak || state.starting_capital),
    state.marked_equity,
  );
  const drawdown =
    state.equity_peak > 0 ? state.marked_equity / state.equity_peak - 1 : 0;
  state.max_drawdown = Math.min(Number(state.max_drawdown || 0), drawdown);
  return drawdown;
}

export function normalizePaperState(row) {
  if (!row) return null;
  return {
    ...row,
    in_position: Boolean(row.in_position),
    pending_entry: Boolean(row.pending_entry),
  };
}

export function processPaperBar(inputState, bar, processedAt = new Date()) {
  const state = normalizePaperState({ ...inputState });
  const processedAtIso = processedAt.toISOString();
  let action = "WAIT";
  let reason = "No 30-minute paper action.";
  let trade = null;

  if (
    state.last_processed_timestamp &&
    bar.timestamp <= state.last_processed_timestamp
  ) {
    return { processed: false, state, decision: null, trade: null, equity: null };
  }

  const hadPositionAtOpen = state.in_position;
  if (hadPositionAtOpen) {
    state.bars_held = Number(state.bars_held || 0) + 1;
    state.position_market_value = state.shares * bar.soxl_close;
    state.marked_equity = state.cash + state.position_market_value;
    state.current_position_return =
      state.entry_price > 0 ? bar.soxl_close / state.entry_price - 1 : 0;

    if (state.bars_held >= PAPER_CONFIG.holdBars) {
      const exitPrice = bar.soxl_close * (1 - PAPER_CONFIG.slippage);
      const finalEquity = state.cash + state.shares * exitPrice;
      const equityBeforeEntry =
        state.equity_before_entry || state.paper_equity;
      const positionReturn =
        state.entry_price > 0 ? exitPrice / state.entry_price - 1 : 0;
      trade = {
        trade_id: crypto.randomUUID(),
        account_id: state.account_id,
        strategy_version: state.strategy_version,
        entry_signal_timestamp: state.entry_signal_timestamp,
        entry_timestamp: state.entry_timestamp,
        exit_timestamp: bar.timestamp,
        entry_price: state.entry_price,
        exit_price: exitPrice,
        shares: state.shares,
        bars_held: state.bars_held,
        position_return: positionReturn,
        account_return: finalEquity / equityBeforeEntry - 1,
        realized_pnl: finalEquity - equityBeforeEntry,
        equity_before_entry: equityBeforeEntry,
        equity_after_exit: finalEquity,
        entry_z: state.entry_z,
        exit_reason: `fixed_hold_${PAPER_CONFIG.holdBars}_30m_bars`,
        created_at: processedAtIso,
      };
      state.paper_equity = finalEquity;
      state.cash = finalEquity;
      state.marked_equity = finalEquity;
      clearPosition(state);
      action = "SELL";
      reason = `Exited after ${PAPER_CONFIG.holdBars} completed 30-minute bars.`;
    } else {
      action = "HOLD";
      reason = `Position open. Holding bar ${state.bars_held} of ${PAPER_CONFIG.holdBars}.`;
    }
  }

  if (!state.in_position && state.pending_entry) {
    const sameSession = state.pending_market_date === bar.market_date;
    if (sameSession && bar.timestamp > state.pending_signal_timestamp) {
      const accountEquity = state.marked_equity;
      const investedCapital =
        accountEquity * PAPER_CONFIG.positionFraction;
      const entryPrice = bar.soxl_open * (1 + PAPER_CONFIG.slippage);
      state.cash = accountEquity - investedCapital;
      state.marked_equity =
        state.cash + (investedCapital / entryPrice) * bar.soxl_close;
      state.in_position = true;
      state.entry_signal_timestamp = state.pending_signal_timestamp;
      state.entry_timestamp = bar.timestamp;
      state.entry_price = entryPrice;
      state.entry_z = state.pending_entry_z;
      state.shares = investedCapital / entryPrice;
      state.invested_capital = investedCapital;
      state.equity_before_entry = accountEquity;
      state.bars_held = 0;
      state.position_market_value = state.shares * bar.soxl_close;
      state.current_position_return = bar.soxl_close / entryPrice - 1;
      clearPending(state);
      action = "BUY";
      reason =
        "Entered at the next completed 30-minute bar open after the signal.";
    } else if (!sameSession) {
      clearPending(state);
      action = "CANCEL_PENDING";
      reason = "Cancelled pending entry at the session boundary.";
    }
  }

  if (!state.in_position && !state.pending_entry && bar.shadow_signal) {
    const canFinishSameSession =
      Number(bar.bar_number) + 1 + PAPER_CONFIG.holdBars <=
      STRATEGY.sessionBars;
    if (canFinishSameSession) {
      state.pending_entry = true;
      state.pending_signal_timestamp = bar.timestamp;
      state.pending_market_date = bar.market_date;
      state.pending_entry_z = bar.soxl_z_5bar;
      action = action === "SELL" ? "SELL_AND_QUEUE_BUY" : "QUEUE_BUY";
      reason =
        "Signal confirmed; queued a paper entry for the next 30-minute bar open.";
    } else if (action === "WAIT") {
      action = "SIGNAL_SKIPPED_TOO_LATE";
      reason =
        "Signal arrived too late for a next-bar-open entry and three-bar same-day hold.";
    }
  }

  if (state.in_position && !hadPositionAtOpen) {
    state.position_market_value = state.shares * bar.soxl_close;
    state.marked_equity = state.cash + state.position_market_value;
  } else if (!state.in_position) {
    state.position_market_value = 0;
    state.current_position_return = 0;
    state.marked_equity = state.paper_equity;
  }

  const drawdown = updateDrawdown(state);
  state.last_processed_timestamp = bar.timestamp;
  state.last_action = action;
  state.last_reason = reason;
  state.updated_at = processedAtIso;

  const decision = {
    account_id: state.account_id,
    timestamp: bar.timestamp,
    processed_at: processedAtIso,
    market_date: bar.market_date,
    strategy_version: state.strategy_version,
    action,
    reason,
    shadow_signal: Boolean(bar.shadow_signal),
    shadow_action: bar.shadow_action,
    soxl_open: bar.soxl_open,
    soxl_close: bar.soxl_close,
    soxl_z_5bar: bar.soxl_z_5bar,
    qqq_from_open_pct: bar.qqq_from_open_pct,
    account_state: accountStateLabel(state),
    pending_entry: state.pending_entry,
    in_position: state.in_position,
    entry_timestamp: state.entry_timestamp,
    entry_price: state.entry_price,
    shares: state.shares,
    bars_held: state.bars_held,
    paper_cash: state.cash,
    paper_realized_equity: state.paper_equity,
    paper_marked_equity: state.marked_equity,
    current_position_return: state.current_position_return,
  };

  const equity = {
    account_id: state.account_id,
    timestamp: bar.timestamp,
    market_date: bar.market_date,
    marked_equity: state.marked_equity,
    realized_equity: state.paper_equity,
    cash: state.cash,
    in_position: state.in_position,
    pending_entry: state.pending_entry,
    drawdown,
  };

  return { processed: true, state, decision, trade, equity };
}
