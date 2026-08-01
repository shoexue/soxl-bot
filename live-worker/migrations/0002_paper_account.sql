CREATE TABLE IF NOT EXISTS paper_accounts (
    account_id TEXT PRIMARY KEY,
    strategy_version TEXT NOT NULL,
    starting_capital REAL NOT NULL,
    paper_equity REAL NOT NULL,
    cash REAL NOT NULL,
    marked_equity REAL NOT NULL,
    in_position INTEGER NOT NULL DEFAULT 0,
    pending_entry INTEGER NOT NULL DEFAULT 0,
    pending_signal_timestamp TEXT,
    pending_market_date TEXT,
    pending_entry_z REAL,
    entry_signal_timestamp TEXT,
    entry_timestamp TEXT,
    entry_price REAL,
    entry_z REAL,
    shares REAL NOT NULL DEFAULT 0,
    invested_capital REAL NOT NULL DEFAULT 0,
    equity_before_entry REAL,
    bars_held INTEGER NOT NULL DEFAULT 0,
    position_market_value REAL NOT NULL DEFAULT 0,
    current_position_return REAL NOT NULL DEFAULT 0,
    last_processed_timestamp TEXT,
    last_action TEXT,
    last_reason TEXT,
    equity_peak REAL NOT NULL,
    max_drawdown REAL NOT NULL DEFAULT 0,
    activated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_decisions (
    account_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    market_date TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    shadow_signal INTEGER NOT NULL DEFAULT 0,
    shadow_action TEXT,
    soxl_open REAL,
    soxl_close REAL,
    soxl_z_5bar REAL,
    qqq_from_open_pct REAL,
    account_state TEXT NOT NULL,
    pending_entry INTEGER NOT NULL DEFAULT 0,
    in_position INTEGER NOT NULL DEFAULT 0,
    entry_timestamp TEXT,
    entry_price REAL,
    shares REAL NOT NULL DEFAULT 0,
    bars_held INTEGER NOT NULL DEFAULT 0,
    paper_cash REAL NOT NULL,
    paper_realized_equity REAL NOT NULL,
    paper_marked_equity REAL NOT NULL,
    current_position_return REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_paper_decisions_timestamp
ON paper_decisions (account_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    entry_signal_timestamp TEXT,
    entry_timestamp TEXT NOT NULL,
    exit_timestamp TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    shares REAL NOT NULL,
    bars_held INTEGER NOT NULL,
    position_return REAL NOT NULL,
    account_return REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    equity_before_entry REAL NOT NULL,
    equity_after_exit REAL NOT NULL,
    entry_z REAL,
    exit_reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_timestamp
ON paper_trades (account_id, exit_timestamp DESC);

CREATE TABLE IF NOT EXISTS paper_equity (
    account_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    market_date TEXT NOT NULL,
    marked_equity REAL NOT NULL,
    realized_equity REAL NOT NULL,
    cash REAL NOT NULL,
    in_position INTEGER NOT NULL DEFAULT 0,
    pending_entry INTEGER NOT NULL DEFAULT 0,
    drawdown REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_paper_equity_timestamp
ON paper_equity (account_id, timestamp DESC);
