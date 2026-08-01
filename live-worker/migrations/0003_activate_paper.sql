INSERT OR IGNORE INTO paper_accounts (
    account_id,
    strategy_version,
    starting_capital,
    paper_equity,
    cash,
    marked_equity,
    in_position,
    pending_entry,
    pending_signal_timestamp,
    pending_market_date,
    pending_entry_z,
    entry_signal_timestamp,
    entry_timestamp,
    entry_price,
    entry_z,
    shares,
    invested_capital,
    equity_before_entry,
    bars_held,
    position_market_value,
    current_position_return,
    last_processed_timestamp,
    last_action,
    last_reason,
    equity_peak,
    max_drawdown,
    activated_at,
    updated_at
)
SELECT
    'fast_30m_live_v1',
    'fast_30m_validated_v4',
    10000.0,
    10000.0,
    10000.0,
    10000.0,
    0,
    0,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.0,
    0.0,
    NULL,
    0,
    0.0,
    0.0,
    latest.timestamp,
    'ACTIVATED',
    'Forward-only $10,000 paper account activated.',
    10000.0,
    0.0,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
FROM (
    SELECT timestamp
    FROM signal_bars
    ORDER BY timestamp DESC
    LIMIT 1
) AS latest;

INSERT OR IGNORE INTO paper_decisions (
    account_id,
    timestamp,
    processed_at,
    market_date,
    strategy_version,
    action,
    reason,
    shadow_signal,
    shadow_action,
    soxl_open,
    soxl_close,
    soxl_z_5bar,
    qqq_from_open_pct,
    account_state,
    pending_entry,
    in_position,
    entry_timestamp,
    entry_price,
    shares,
    bars_held,
    paper_cash,
    paper_realized_equity,
    paper_marked_equity,
    current_position_return
)
SELECT
    account.account_id,
    account.last_processed_timestamp,
    account.activated_at,
    signal.market_date,
    account.strategy_version,
    'ACTIVATED',
    account.last_reason,
    0,
    signal.shadow_action,
    signal.soxl_open,
    signal.soxl_close,
    signal.soxl_z_5bar,
    signal.qqq_from_open_pct,
    'flat',
    0,
    0,
    NULL,
    NULL,
    0.0,
    0,
    10000.0,
    10000.0,
    10000.0,
    0.0
FROM paper_accounts AS account
JOIN signal_bars AS signal
  ON signal.timestamp = account.last_processed_timestamp
WHERE account.account_id = 'fast_30m_live_v1';

INSERT OR IGNORE INTO paper_equity (
    account_id,
    timestamp,
    market_date,
    marked_equity,
    realized_equity,
    cash,
    in_position,
    pending_entry,
    drawdown
)
SELECT
    account.account_id,
    account.last_processed_timestamp,
    signal.market_date,
    10000.0,
    10000.0,
    10000.0,
    0,
    0,
    0.0
FROM paper_accounts AS account
JOIN signal_bars AS signal
  ON signal.timestamp = account.last_processed_timestamp
WHERE account.account_id = 'fast_30m_live_v1';
