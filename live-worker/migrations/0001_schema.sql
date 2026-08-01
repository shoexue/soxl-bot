CREATE TABLE IF NOT EXISTS market_bars (
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    local_datetime TEXT NOT NULL,
    market_date TEXT NOT NULL,
    interval TEXT NOT NULL DEFAULT '30min',
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'twelve_data',
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_timestamp
ON market_bars (symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS signal_bars (
    timestamp TEXT PRIMARY KEY,
    local_datetime TEXT NOT NULL,
    market_date TEXT NOT NULL,
    interval TEXT NOT NULL DEFAULT '30min',
    strategy_version TEXT NOT NULL,
    soxl_open REAL NOT NULL,
    soxl_high REAL NOT NULL,
    soxl_low REAL NOT NULL,
    soxl_close REAL NOT NULL,
    soxl_volume REAL NOT NULL DEFAULT 0,
    soxl_vwap REAL,
    soxl_return_30m_pct REAL,
    soxl_z_5bar REAL,
    soxl_vs_vwap_pct REAL,
    soxl_from_open_pct REAL,
    soxl_from_high_pct REAL,
    soxl_from_low_pct REAL,
    soxl_session_range_pct REAL,
    soxl_session_high REAL,
    soxl_session_low REAL,
    bar_number INTEGER NOT NULL,
    qqq_close REAL NOT NULL,
    qqq_return_30m_pct REAL,
    qqq_from_open_pct REAL,
    bars_in_window INTEGER NOT NULL DEFAULT 1,
    oversold_30m INTEGER NOT NULL DEFAULT 0,
    episode_start_30m INTEGER NOT NULL DEFAULT 0,
    bars_since_episode_start_30m INTEGER,
    bounce_confirmed_30m INTEGER NOT NULL DEFAULT 0,
    regime_ok_30m INTEGER NOT NULL DEFAULT 0,
    entry_window_ok_30m INTEGER NOT NULL DEFAULT 0,
    shadow_signal INTEGER NOT NULL DEFAULT 0,
    shadow_action TEXT NOT NULL,
    shadow_reason TEXT NOT NULL,
    calculated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signal_bars_market_date_timestamp
ON signal_bars (market_date, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_signal_bars_shadow_signal
ON signal_bars (shadow_signal, timestamp DESC);

CREATE TABLE IF NOT EXISTS refresh_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    soxl_rows INTEGER NOT NULL DEFAULT 0,
    qqq_rows INTEGER NOT NULL DEFAULT 0,
    aligned_rows INTEGER NOT NULL DEFAULT 0,
    latest_bar_timestamp TEXT
);

CREATE INDEX IF NOT EXISTS idx_refresh_runs_started_at
ON refresh_runs (started_at DESC);
