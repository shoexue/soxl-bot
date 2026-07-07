import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function formatCurrency(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(number)
}

function formatPercent(value, digits = 1) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return `${(number * 100).toFixed(digits)}%`
}

function formatNumber(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return number.toFixed(digits)
}

function formatDate(value) {
  if (!value || value === 'nan') return 'n/a'
  return String(value).slice(0, 10)
}

function shortText(value, fallback = 'None') {
  if (value === null || value === undefined || value === '' || value === 'nan') {
    return fallback
  }
  return String(value)
}

function statusTone(action = '') {
  const text = action.toUpperCase()
  if (text.includes('BUY')) return 'accent'
  if (text.includes('SELL')) return 'positive'
  if (text.includes('ERROR')) return 'negative'
  if (text.includes('HOLD')) return 'warning'
  if (text.includes('NO NEW DATA')) return 'neutral'
  return 'quiet'
}

function MetricCard({ label, value, detail, tone = 'quiet' }) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </div>
  )
}

function Section({ title, subtitle, children, action }) {
  return (
    <section className="section">
      <div className="section-header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {action ? <div className="section-action">{action}</div> : null}
      </div>
      {children}
    </section>
  )
}

function StatusPill({ children, tone = 'quiet' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>
}

function LoadingState() {
  return (
    <main className="shell">
      <div className="topbar">
        <div>
          <p className="eyebrow">SOXL Paper Bot</p>
          <h1>Loading dashboard</h1>
        </div>
      </div>
      <div className="loading-grid">
        <div />
        <div />
        <div />
      </div>
    </main>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <main className="shell">
      <div className="topbar">
        <div>
          <p className="eyebrow">SOXL Paper Bot</p>
          <h1>Dashboard unavailable</h1>
          <p className="muted">
            Start the API with <code>uvicorn api.server:app --reload</code>, then
            retry.
          </p>
        </div>
        <button className="button" type="button" onClick={onRetry}>
          Retry
        </button>
      </div>
      <div className="notice notice-negative">{message}</div>
    </main>
  )
}

function DashboardHeader({ dashboard, refreshedAt, onRefresh }) {
  const latest = dashboard.latest_daily_log || {}
  const state = dashboard.state || {}
  const action = latest.next_action || state.last_action || 'Unknown'

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">SOXL Paper Bot</p>
        <h1>Paper Trading Dashboard</h1>
        <p className="muted">
          Read-only view of live paper logs, signal state, and historical context.
        </p>
      </div>
      <div className="topbar-side">
        <StatusPill tone={statusTone(action)}>{action}</StatusPill>
        <button className="button" type="button" onClick={onRefresh}>
          Refresh
        </button>
        <span className="refresh-time">Updated {refreshedAt}</span>
      </div>
    </header>
  )
}

function inferAccountState(state) {
  if (state?.in_position) return 'in_position'
  if (state?.pending_entry) return 'pending_entry'
  return 'flat'
}

function signalChecks(dashboard) {
  const latest = dashboard.latest_daily_log || {}
  const signalZ = Number(latest.soxl_z_score)
  const threshold = dashboard.historical?.summary?.z_threshold ?? -1.5

  return [
    ['SOXL z-score < -1.50', Number.isFinite(signalZ) && signalZ < Number(threshold)],
    ['First oversold episode day', latest.episode_start === true],
    ['QQQ above 50-day MA', latest.qqq_above_ma50 === true],
    ['Buy signal', latest.buy_signal === true],
  ]
}

function ActionStrip({ dashboard }) {
  const latest = dashboard.latest_daily_log || {}
  const state = dashboard.state || {}
  const performance = dashboard.performance || {}
  const market = dashboard.market || {}
  const latestMarket = market.latest || {}
  const action = latest.next_action || state.last_action || 'Unknown'
  const accountState = latest.account_state || inferAccountState(state)

  return (
    <div className="action-strip">
      <div className={`command-panel command-${statusTone(action)}`}>
        <span>Next Action</span>
        <strong>{shortText(action, 'Unknown')}</strong>
        <p>{shortText(latest.reason || state.last_reason, 'No reason logged')}</p>
      </div>
      <div className="action-facts">
        <div>
          <span>SOXL Close</span>
          <strong>{formatCurrency(latestMarket.close || latest.soxl_close)}</strong>
        </div>
        <div>
          <span>Market Date</span>
          <strong>{formatDate(latestMarket.date || latest.market_date || state.last_processed_market_date)}</strong>
        </div>
        <div>
          <span>State</span>
          <strong>{shortText(accountState)}</strong>
        </div>
        <div>
          <span>Marked Equity</span>
          <strong>{formatCurrency(performance.current_marked_equity)}</strong>
        </div>
      </div>
    </div>
  )
}

function PerformancePanel({ dashboard }) {
  const performance = dashboard.performance || {}
  const curve = performance.equity_curve || []
  const state = dashboard.state || {}
  const latest = dashboard.latest_daily_log || {}
  const checks = signalChecks(dashboard)

  return (
    <section className="console-section">
      <ActionStrip dashboard={dashboard} />

      <div className="console-grid">
        <div className="console-main">
          <div className="chart-box console-chart">
            <div className="console-chart-header">
              <div>
                <h2>Paper Equity</h2>
                <p>Marked daily equity from forward paper trading.</p>
              </div>
              <StatusPill tone={state.in_position ? 'warning' : state.pending_entry ? 'accent' : 'quiet'}>
                {state.in_position ? 'In Position' : state.pending_entry ? 'Pending Entry' : 'Flat'}
              </StatusPill>
            </div>
            {curve.length ? (
              <ResponsiveContainer width="100%" height={390}>
                <LineChart data={curve} margin={{ top: 12, right: 20, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="rgba(226, 232, 240, 0.16)" vertical={false} />
                  <XAxis dataKey="market_date" tick={{ fontSize: 12 }} minTickGap={28} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    width={64}
                    domain={['dataMin - 100', 'dataMax + 100']}
                    tickFormatter={(value) => `$${Math.round(value / 1000)}k`}
                  />
                  <Tooltip formatter={(value) => formatCurrency(value)} />
                  <ReferenceLine y={10000} stroke="rgba(226, 232, 240, 0.36)" strokeDasharray="4 4" />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke="#7dd3fc"
                    strokeWidth={3}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="No equity curve yet" text="Daily paper logs will populate this chart." />
            )}
          </div>

          <div className="metric-grid performance-metrics">
            <MetricCard
              label="Marked Equity"
              value={formatCurrency(performance.current_marked_equity)}
              detail={`Cash ${formatCurrency(performance.cash)}`}
            />
            <MetricCard
              label="Total Return"
              value={formatPercent(performance.total_account_return)}
              detail={`${performance.closed_trades || 0} closed paper trades`}
              tone={Number(performance.total_account_return) >= 0 ? 'positive' : 'negative'}
            />
            <MetricCard
              label="Current Drawdown"
              value={formatPercent(performance.current_drawdown)}
              detail={`Max ${formatPercent(performance.max_mark_to_market_drawdown)}`}
              tone={Number(performance.current_drawdown) < 0 ? 'warning' : 'quiet'}
            />
            <MetricCard
              label="Open Position"
              value={state.in_position ? 'Open' : 'None'}
              detail={
                state.in_position
                  ? `${formatNumber(state.shares, 4)} shares from ${formatDate(state.entry_date)}`
                  : 'Waiting for signal'
              }
              tone={state.in_position ? 'warning' : 'quiet'}
            />
          </div>
        </div>

        <aside className="console-side">
          <div className="side-card">
            <h3>Signal Now</h3>
            <div className="zscore side-zscore">
              <span>SOXL 5D z-score</span>
              <strong>{formatNumber(latest.soxl_z_score, 3)}</strong>
            </div>
            <div className="check-list side-checks">
              {checks.map(([label, passed]) => (
                <div className="check-row" key={label}>
                  <span className={`check-dot ${passed ? 'check-pass' : 'check-fail'}`} />
                  <span>{label}</span>
                  <strong>{passed ? 'Yes' : 'No'}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="side-card">
            <h3>Market Snapshot</h3>
            <div className="side-facts">
              <div><span>SOXL close</span><strong>{formatCurrency(latest.soxl_close)}</strong></div>
              <div><span>QQQ close</span><strong>{formatCurrency(latest.qqq_close)}</strong></div>
              <div><span>QQQ MA50</span><strong>{formatCurrency(latest.qqq_ma50)}</strong></div>
              <div><span>Signal date</span><strong>{formatDate(state.signal_date)}</strong></div>
            </div>
          </div>

          <div className="side-card">
            <h3>Position</h3>
            <div className="side-facts">
              <div><span>Status</span><strong>{state.in_position ? 'Open' : state.pending_entry ? 'Pending' : 'Flat'}</strong></div>
              <div><span>Entry</span><strong>{formatDate(state.entry_date)}</strong></div>
              <div><span>Entry price</span><strong>{formatCurrency(state.entry_price)}</strong></div>
              <div><span>Days held</span><strong>{shortText(state.days_held, '0')}</strong></div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}

function MarketHistoryPanel({ dashboard }) {
  const market = dashboard.market || {}
  const prices = market.prices || []
  const markers = market.markers || {}
  const signals = (markers.signals || []).filter((row) => row.close)
  const entries = (markers.entries || []).filter((row) => row.close)
  const exits = (markers.exits || []).filter((row) => row.close)
  const signalsByDate = new Map(signals.map((row) => [row.date, row]))
  const entriesByDate = new Map(entries.map((row) => [row.date, row]))
  const exitsByDate = new Map(exits.map((row) => [row.date, row]))
  const chartRows = prices.map((row) => {
    const signal = signalsByDate.get(row.date)
    const entry = entriesByDate.get(row.date)
    const exit = exitsByDate.get(row.date)

    return {
      ...row,
      signal_close: signal?.close ?? null,
      entry_close: entry?.close ?? null,
      exit_close: exit?.close ?? null,
    }
  })
  const latest = market.latest || {}

  return (
    <Section
      title="SOXL Price And Frozen Signals"
      subtitle="Adjusted daily SOXL history with the historical signal, entry, and exit points for this frozen strategy."
    >
      <div className="market-layout">
        <div className="chart-box market-chart">
          {prices.length ? (
            <ResponsiveContainer width="100%" height={360}>
              <ComposedChart data={chartRows} margin={{ top: 12, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(226, 232, 240, 0.13)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={32} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  width={64}
                  domain={['dataMin - 8', 'dataMax + 8']}
                  tickFormatter={(value) => `$${Math.round(value)}`}
                />
                <Tooltip
                  formatter={(value, name) => [
                    name === 'position_return' ? formatPercent(value, 2) : formatCurrency(value),
                    name,
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="close"
                  name="SOXL close"
                  stroke="#dbeafe"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Scatter dataKey="signal_close" name="Signal" fill="#fbbf24" />
                <Scatter dataKey="entry_close" name="Entry" fill="#67d7f0" />
                <Scatter dataKey="exit_close" name="Exit" fill="#4fd1a1" />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="No SOXL history found" text="The API could not read data/SOXL.csv." />
          )}
        </div>

        <aside className="legend-card">
          <div>
            <span className="legend-label">Latest Completed Close</span>
            <strong>{formatCurrency(latest.close)}</strong>
            <p>{formatDate(latest.date)} from {shortText(market.price_source, 'local daily data')}</p>
          </div>
          <div className="marker-legend">
            <div><span className="marker marker-signal" /> Signal after close</div>
            <div><span className="marker marker-entry" /> Next-open entry</div>
            <div><span className="marker marker-exit" /> Day-4 close exit</div>
          </div>
          <div className="decision-note">
            <h3>Decision Use</h3>
            <p>
              Use this to see where the frozen rules acted historically. The live action
              still comes from the top console after a completed daily close.
            </p>
          </div>
        </aside>
      </div>
    </Section>
  )
}

function HistoricalPanel({ dashboard }) {
  const historical = dashboard.historical || {}
  const summary = historical.summary || {}
  const walkForward = historical.walk_forward || {}
  const returnPath = historical.return_path || []
  const frequency = historical.signal_frequency || {}
  const bars = returnPath.map((row) => ({
    day: `Day ${row.day}`,
    return: Number(row.avg_cumulative_return),
  }))

  return (
    <Section
      title="Historical Context"
      subtitle="Reference data from prior research. Useful context, not a promise."
    >
      <div className="metric-grid historical-grid">
        <MetricCard
          label="Historical Trades"
          value={summary.trades || 'n/a'}
          detail={`Signals: ${frequency.count || 0}`}
        />
        <MetricCard
          label="Avg Position Return"
          value={formatPercent(summary.avg_position_return)}
          detail={`Median ${formatPercent(summary.median_position_return)}`}
          tone="positive"
        />
        <MetricCard
          label="Historical Win Rate"
          value={formatPercent(summary.win_rate)}
          detail={`Worst ${formatPercent(summary.worst_trade)}`}
        />
        <MetricCard
          label="Walk-Forward OOS"
          value={formatPercent(walkForward.oos_avg_return)}
          detail={`${walkForward.oos_trades || 0} trades, ${formatPercent(walkForward.oos_win_rate)} win rate`}
        />
      </div>

      <div className="two-column">
        <div className="chart-box compact">
          <h3>Average Return Path</h3>
          {bars.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={bars} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(226, 232, 240, 0.14)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} width={44} />
                <Tooltip formatter={(value) => formatPercent(value, 2)} />
                <ReferenceLine y={0} stroke="rgba(226, 232, 240, 0.3)" />
                <Bar dataKey="return" radius={[4, 4, 0, 0]}>
                  {bars.map((bar) => (
                    <Cell key={bar.day} fill={bar.return >= 0 ? '#5eead4' : '#fbbf24'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="Return path missing" text="No historical path data found." />
          )}
        </div>
        <div className="frequency-box">
          <h3>Signal Frequency By Year</h3>
          <div className="frequency-list">
            {Object.entries(frequency.by_year || {}).map(([year, count]) => (
              <div className="frequency-row" key={year}>
                <span>{year}</span>
                <div className="frequency-track">
                  <div
                    className="frequency-fill"
                    style={{ width: `${Math.min(100, Number(count) * 12)}%` }}
                  />
                </div>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
          <p className="muted small">
            Average frequency: {formatNumber(frequency.avg_per_year, 2)} signals per active
            year in the historical sample.
          </p>
        </div>
      </div>
    </Section>
  )
}

function LogsPanel({ dashboard }) {
  const rows = dashboard.recent_daily_log || []
  const trades = dashboard.recent_trades || []
  const paperSignals = dashboard.paper_signals || []

  return (
    <Section
      title="Signals And Logs"
      subtitle="Recent bot decisions and paper trades."
    >
      <div className="three-column">
        <DataTable
          title="Recent Runs"
          rows={rows.slice(-8).reverse()}
          columns={[
            ['market_date', 'Date'],
            ['next_action', 'Action'],
            ['soxl_z_score', 'Z'],
            ['buy_signal', 'Signal'],
          ]}
          formatters={{
            soxl_z_score: (value) => formatNumber(value, 3),
            buy_signal: (value) => (value ? 'Yes' : 'No'),
          }}
        />
        <DataTable
          title="Paper Signals"
          rows={paperSignals.slice(-8).reverse()}
          columns={[
            ['market_date', 'Signal Date'],
            ['soxl_z_score', 'Z'],
            ['next_action', 'Action'],
          ]}
          formatters={{
            soxl_z_score: (value) => formatNumber(value, 3),
          }}
          emptyText="No forward paper signals logged yet."
        />
        <DataTable
          title="Closed Trades"
          rows={trades.slice(-8).reverse()}
          columns={[
            ['entry_date', 'Entry'],
            ['exit_date', 'Exit'],
            ['position_return', 'Return'],
          ]}
          formatters={{
            position_return: (value) => formatPercent(value, 2),
          }}
          emptyText="No closed paper trades yet."
        />
      </div>
    </Section>
  )
}

function DataHealthPanel({ dashboard }) {
  const health = dashboard.data_health || {}
  const files = health.files || {}
  const duplicates = health.duplicate_market_dates || []

  return (
    <Section
      title="Reliability"
      subtitle="File freshness, duplicate-run warnings, and local data coverage."
    >
      <div className="health-grid">
        {Object.entries(files).map(([name, file]) => (
          <div className="health-row" key={name}>
            <span>{name}</span>
            <strong>{file.exists ? 'Present' : 'Missing'}</strong>
            <em>{file.latest_date || file.last_processed_market_date || `${file.rows ?? file.keys ?? 0} rows`}</em>
          </div>
        ))}
      </div>
      {duplicates.length ? (
        <div className="notice notice-warning">
          Duplicate market-date rows found: {duplicates.map((row) => row.market_date).join(', ')}
        </div>
      ) : (
        <div className="notice notice-positive">No duplicate market-date rows reported.</div>
      )}
    </Section>
  )
}

function DataTable({ title, rows, columns, formatters = {}, emptyText = 'No rows yet.' }) {
  return (
    <div className="table-panel">
      <h3>{title}</h3>
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map(([, label]) => (
                  <th key={label}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`${title}-${rowIndex}`}>
                  {columns.map(([key]) => {
                    const formatter = formatters[key]
                    const value = formatter ? formatter(row[key]) : shortText(row[key], 'n/a')
                    return <td key={key}>{value}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title={emptyText} />
      )}
    </div>
  )
}

function EmptyState({ title, text }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {text ? <span>{text}</span> : null}
    </div>
  )
}

function App() {
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshedAt, setRefreshedAt] = useState('')

  const loadDashboard = useCallback(async () => {
    setError('')
    try {
      const response = await fetch(`${API_BASE}/api/dashboard`)
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`)
      }
      const payload = await response.json()
      setDashboard(payload)
      setRefreshedAt(new Date().toLocaleTimeString())
    } catch (loadError) {
      setError(loadError.message || 'Unable to load dashboard.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(loadDashboard, 0)
    return () => window.clearTimeout(timer)
  }, [loadDashboard])

  const page = useMemo(() => {
    if (loading) return <LoadingState />
    if (error) return <ErrorState message={error} onRetry={loadDashboard} />
    if (!dashboard) return <ErrorState message="No dashboard payload returned." onRetry={loadDashboard} />

    return (
      <main className="shell">
        <DashboardHeader
          dashboard={dashboard}
          refreshedAt={refreshedAt}
          onRefresh={loadDashboard}
        />
        <PerformancePanel dashboard={dashboard} />
        <MarketHistoryPanel dashboard={dashboard} />
        <HistoricalPanel dashboard={dashboard} />
        <LogsPanel dashboard={dashboard} />
        <DataHealthPanel dashboard={dashboard} />
      </main>
    )
  }, [dashboard, error, loadDashboard, loading, refreshedAt])

  return page
}

export default App
