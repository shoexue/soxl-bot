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

const DEFAULT_API_BASE = 'http://127.0.0.1:8000'
const API_BASE = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE
const LIVE_API_BASE = String(import.meta.env.VITE_LIVE_API_BASE_URL || '').replace(/\/$/, '')
const LIVE_DASHBOARD_URL = LIVE_API_BASE ? `${LIVE_API_BASE}/api/dashboard` : ''
const LIVE_REFRESH_MS = 60_000
const USE_STATIC_DASHBOARD = import.meta.env.PROD && !import.meta.env.VITE_API_BASE_URL
const READS_STATIC_DASHBOARD = Boolean(import.meta.env.VITE_DASHBOARD_JSON_URL) || USE_STATIC_DASHBOARD
const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_JSON_URL
  || (USE_STATIC_DASHBOARD ? `${import.meta.env.BASE_URL}data/dashboard.json` : `${API_BASE}/api/dashboard`)

function mergeLiveDashboard(basePayload, livePayload, liveError = '') {
  const baseIntraday = basePayload.intraday || {}
  const liveIntraday = livePayload?.intraday || {}
  const baseThirtyMinute = baseIntraday.thirty_minute || {}
  const liveThirtyMinute = liveIntraday.thirty_minute || {}

  return {
    ...basePayload,
    intraday: livePayload
      ? {
          ...baseIntraday,
          ...liveIntraday,
          overnight_rebound_paper:
            baseIntraday.overnight_rebound_paper || liveIntraday.overnight_rebound_paper,
          thirty_minute: {
            ...baseThirtyMinute,
            ...liveThirtyMinute,
            adaptive_challenger:
              baseThirtyMinute.adaptive_challenger || liveThirtyMinute.adaptive_challenger,
            backtest: baseThirtyMinute.backtest || liveThirtyMinute.backtest,
          },
        }
      : baseIntraday,
    data_health: {
      ...(basePayload.data_health || {}),
      live_api: livePayload?.data_health || null,
    },
    live_api: {
      enabled: Boolean(LIVE_DASHBOARD_URL),
      connected: Boolean(livePayload),
      url: LIVE_DASHBOARD_URL,
      fetched_at: livePayload ? new Date().toISOString() : null,
      latest_refresh: livePayload?.data_health?.latest_refresh || null,
      error: liveError,
    },
  }
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === '') return 'n/a'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(number)
}

function formatPrice(value) {
  if (value === null || value === undefined || value === '') return 'n/a'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number)
}

function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || value === '') return 'n/a'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return `${(number * 100).toFixed(digits)}%`
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return 'n/a'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'n/a'
  return number.toFixed(digits)
}

function formatDate(value) {
  if (!value || value === 'nan') return 'n/a'
  return String(value).slice(0, 10)
}

function formatDateTime(value) {
  if (!value || value === 'nan') return 'n/a'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString()
}

function formatClock(value) {
  if (!value || value === 'nan') return 'n/a'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(11, 16)
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function shortText(value, fallback = 'None') {
  if (value === null || value === undefined || value === '' || value === 'nan') {
    return fallback
  }
  return String(value)
}

function statusTone(action = '') {
  const text = String(action || '').toUpperCase()
  if (text === 'SUCCESS' || text === 'COMPLETED') return 'positive'
  if (text === 'FAILURE' || text === 'FAILED' || text === 'ERROR') return 'negative'
  if (text === 'CANCELLED' || text === 'SKIPPED' || text === 'STALE') return 'warning'
  if (
    text.includes('EXTREME')
    || text.includes('PULLBACK')
    || text.includes('BOUNCE')
    || text.includes('TREND')
  ) return 'warning'
  if (text.includes('SHADOW')) return 'accent'
  if (text.includes('OVERSOLD')) return 'warning'
  if (text.includes('REGIME')) return 'warning'
  if (text.includes('OBSERVE')) return 'quiet'
  if (text.includes('BUY')) return 'accent'
  if (text.includes('SELL')) return 'positive'
  if (text.includes('ERROR')) return 'negative'
  if (text.includes('HOLD')) return 'warning'
  if (text.includes('NO NEW DATA')) return 'neutral'
  return 'quiet'
}

function signedTone(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'quiet'
  return number >= 0 ? 'positive' : 'negative'
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
          {READS_STATIC_DASHBOARD ? (
            <p className="muted">
              The hosted dashboard could not load <code>data/dashboard.json</code>.
            </p>
          ) : (
            <p className="muted">
              Start the API with <code>uvicorn api.server:app --reload</code>, then
              retry.
            </p>
          )}
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
  const fastPaper = dashboard.intraday?.thirty_minute?.paper || {}
  const fastState = fastPaper.state || {}
  const latestClosedTrade = (fastPaper.trades || []).at(-1)
  const action = fastState.in_position
    ? 'BUY · Position open'
    : fastState.pending_entry
      ? 'BUY queued'
      : latestClosedTrade
        ? 'Flat · Last SELL'
        : fastPaper.active
          ? 'Flat · Scanning'
          : 'Offline'

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">SOXL Strategy Lab</p>
        <h1>Paper trading, at two speeds.</h1>
        <p className="muted topbar-copy">
          The live 30-minute strategy leads. The slower daily strategy and its long-term
          evidence follow below.
        </p>
        <nav className="strategy-nav" aria-label="Dashboard sections">
          <a href="#fast-strategy"><span className="nav-dot nav-dot-fast" />30-minute</a>
          <a href="#slow-strategy"><span className="nav-dot nav-dot-slow" />Daily</a>
        </nav>
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

function StrategyStep({ number, title, text, tone = 'fast' }) {
  return (
    <div className={`strategy-step strategy-step-${tone}`}>
      <span>{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  )
}

function ConditionCard({ label, value, detail, passed, active = false }) {
  const tone = passed ? 'positive' : active ? 'warning' : 'quiet'
  return (
    <div className={`condition-card condition-${tone}`}>
      <div className="condition-topline">
        <span className={`condition-light condition-light-${tone}`} />
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  )
}

function buildPaperExecutions(trades = [], state = {}) {
  const executions = trades.flatMap((trade) => [
    {
      id: `${trade.trade_id}-buy`,
      side: 'BUY',
      timestamp: trade.entry_timestamp,
      price: Number(trade.entry_price),
      shares: Number(trade.shares),
      notional: Number(trade.entry_price) * Number(trade.shares),
      status: 'Entry filled',
      realizedPnl: null,
      positionReturn: Number(trade.position_return),
      pairedExitPrice: Number(trade.exit_price),
    },
    {
      id: `${trade.trade_id}-sell`,
      side: 'SELL',
      timestamp: trade.exit_timestamp,
      price: Number(trade.exit_price),
      shares: Number(trade.shares),
      notional: Number(trade.exit_price) * Number(trade.shares),
      status: 'Exit filled',
      realizedPnl: Number(trade.realized_pnl),
      positionReturn: Number(trade.position_return),
    },
  ])

  if (state.in_position && state.entry_timestamp && state.entry_price && state.shares) {
    executions.push({
      id: `open-${state.entry_timestamp}`,
      side: 'BUY',
      timestamp: state.entry_timestamp,
      price: Number(state.entry_price),
      shares: Number(state.shares),
      notional: Number(state.entry_price) * Number(state.shares),
      status: 'Position open',
      realizedPnl: null,
      positionReturn: Number(state.current_position_return),
    })
  }

  return executions.sort(
    (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
  )
}

function ExecutionTape({ executions }) {
  if (!executions.length) {
    return (
      <div className="execution-empty">
        <strong>No BUY or SELL fills yet</strong>
        <span>The first executed paper order will appear here with its price and quantity.</span>
      </div>
    )
  }

  return (
    <div className="execution-tape">
      {executions.slice(0, 10).map((execution) => (
        <article className={`execution-row execution-${execution.side.toLowerCase()}`} key={execution.id}>
          <div className="execution-identity">
            <span className={`execution-side execution-side-${execution.side.toLowerCase()}`}>
              {execution.side}
            </span>
            <div>
              <strong>{formatDateTime(execution.timestamp)}</strong>
              <span>{execution.status}</span>
            </div>
          </div>
          <div className="execution-stat">
            <span>Fill price</span>
            <strong>{formatPrice(execution.price)}</strong>
          </div>
          <div className="execution-stat">
            <span>Quantity</span>
            <strong>{formatNumber(execution.shares, 3)} shares</strong>
          </div>
          <div className="execution-stat">
            <span>Value</span>
            <strong>{formatCurrency(execution.notional)}</strong>
          </div>
          <div className="execution-stat execution-result">
            <span>{execution.side === 'SELL' ? 'Realized result' : 'Position status'}</span>
            <strong className={execution.realizedPnl === null ? '' : `value-${signedTone(execution.realizedPnl)}`}>
              {execution.realizedPnl === null
                ? execution.status === 'Position open'
                  ? `${formatPercent(execution.positionReturn, 2)} open`
                  : `Sold at ${formatPrice(execution.pairedExitPrice)} · ${formatPercent(execution.positionReturn, 2)}`
                : `${formatCurrency(execution.realizedPnl)} · ${formatPercent(execution.positionReturn, 2)}`}
            </strong>
          </div>
        </article>
      ))}
    </div>
  )
}

function FastStrategyPanel({ dashboard }) {
  const intraday = dashboard.intraday || {}
  const thirtyMinute = intraday.thirty_minute || {}
  const latest = thirtyMinute.latest || {}
  const latestSignal = thirtyMinute.latest_signal || {}
  const paper = thirtyMinute.paper || {}
  const summary = paper.summary || {}
  const state = paper.state || {}
  const bars = thirtyMinute.bars || intraday.bars || []
  const equity = paper.equity_curve || []
  const trades = paper.trades || []
  const executions = buildPaperExecutions(trades, state)
  const latestExecution = executions[0] || null
  const closedTrades = Number(summary.closed_trades || 0)
  const signalCount = Number(thirtyMinute.signal_count || 0)
  const paperStatus = state.in_position
    ? 'In position'
    : state.pending_entry
      ? 'Entry queued'
      : paper.active
        ? 'Flat · watching'
        : 'Not active'
  const engineAction = shortText(latest.shadow_action, paperStatus)
  const action = latestExecution?.side || (state.pending_entry ? 'BUY QUEUED' : 'NO FILLS YET')
  const actionReason = latestExecution
    ? `${latestExecution.side === 'BUY' ? 'Bought' : 'Sold'} ${formatNumber(latestExecution.shares, 3)} shares at ${formatPrice(latestExecution.price)} on ${formatDateTime(latestExecution.timestamp)}.`
    : 'The account is active and scanning, but no paper order has filled yet.'
  const zScore = Number(latest.soxl_z_5bar)
  const stretchTriggered = Number.isFinite(zScore) && zScore <= -1.25
  const liveApi = dashboard.live_api || {}
  const hasMarketBars = bars.length > 0

  return (
    <section className="strategy-section strategy-section-fast" id="fast-strategy">
      <div className="strategy-kicker-row">
        <div>
          <p className="strategy-kicker"><span>01</span> Fast strategy</p>
          <h2>30-minute mean-reversion paper trader</h2>
          <p className="strategy-summary">
            Looks for a sharp SOXL pullback, waits for the first convincing bounce, and
            trades only while QQQ and the remaining session provide enough support.
          </p>
        </div>
        <div className="strategy-status-stack">
          <StatusPill tone={liveApi.connected ? 'positive' : 'warning'}>
            {liveApi.connected ? 'Live cloud feed' : 'Feed unavailable'}
          </StatusPill>
          <span>Last bar {formatDateTime(summary.last_processed_timestamp || latest.timestamp)}</span>
        </div>
      </div>

      <div className="fast-command-grid">
        <div className={`hero-command command-${statusTone(action)}`}>
          <div className="hero-command-label">Most recent paper execution</div>
          <strong>{latestExecution ? `${action} · ${formatPrice(latestExecution.price)}` : action}</strong>
          <p>{actionReason}</p>
          <div className="hero-command-meta">
            <span>Now: {paperStatus}</span>
            <span>Engine: {engineAction}</span>
            <span>{signalCount} signal{signalCount === 1 ? '' : 's'} today</span>
            {latestExecution ? <span>{formatNumber(latestExecution.shares, 3)} shares</span> : null}
          </div>
        </div>

        <div className="strategy-rules">
          <StrategyStep
            number="1"
            title="Find the stretch"
            text="SOXL's 5-bar z-score reaches −1.25 or lower."
          />
          <StrategyStep
            number="2"
            title="Wait for the bounce"
            text="Within two bars, require a green bar and a higher close."
          />
          <StrategyStep
            number="3"
            title="Check the market"
            text="QQQ must be no worse than 1% below its session open."
          />
          <StrategyStep
            number="4"
            title="Paper trade it"
            text="Enter next bar open, use 50%, hold three bars, exit before close."
          />
        </div>
      </div>

      <div className="section-label-row execution-heading">
        <div>
          <span>BUY and SELL executions</span>
          <p>Only filled paper orders are shown—routine WAIT observations are intentionally excluded.</p>
        </div>
        <StatusPill tone={state.in_position ? 'warning' : state.pending_entry ? 'accent' : 'quiet'}>
          Current position: {paperStatus}
        </StatusPill>
      </div>
      <ExecutionTape executions={executions} />

      <div className="section-label-row">
        <div>
          <span>Forward performance</span>
          <p>Real paper decisions since activation—not backfilled research trades.</p>
        </div>
        <StatusPill tone={closedTrades ? signedTone(summary.total_return) : 'accent'}>
          {closedTrades ? `${closedTrades} closed trades` : 'Building sample'}
        </StatusPill>
      </div>
      <div className="metric-grid fast-performance-grid">
        <MetricCard
          label="Marked Equity"
          value={formatCurrency(summary.marked_equity)}
          detail={`Started ${formatCurrency(summary.starting_capital)}`}
          tone={signedTone(summary.total_return)}
        />
        <MetricCard
          label="Total Return"
          value={formatPercent(summary.total_return, 2)}
          detail={`${formatCurrency(summary.realized_pnl)} realized P&L`}
          tone={signedTone(summary.total_return)}
        />
        <MetricCard
          label="Win Rate"
          value={closedTrades ? formatPercent(summary.win_rate, 1) : 'Building'}
          detail={closedTrades ? `${summary.wins || 0} wins from ${closedTrades}` : 'Needs closed trades before it is meaningful'}
          tone={closedTrades ? signedTone(Number(summary.win_rate) - 0.5) : 'accent'}
        />
        <MetricCard
          label="Average Trade"
          value={closedTrades ? formatPercent(summary.avg_position_return, 2) : 'No sample'}
          detail={closedTrades ? `Best ${formatPercent(summary.best_trade, 2)} · worst ${formatPercent(summary.worst_trade, 2)}` : 'Forward trades only'}
          tone={closedTrades ? signedTone(summary.avg_position_return) : 'quiet'}
        />
        <MetricCard
          label="Max Drawdown"
          value={formatPercent(summary.max_drawdown, 2)}
          detail="Peak-to-trough marked account loss"
          tone={Number(summary.max_drawdown) < -0.03 ? 'negative' : 'positive'}
        />
        <MetricCard
          label="Current Exposure"
          value={formatPercent(summary.exposure, 0)}
          detail={state.in_position ? `${formatNumber(state.shares, 3)} SOXL shares` : 'No open position'}
          tone={state.in_position ? 'warning' : 'quiet'}
        />
      </div>

      <div className="section-label-row">
        <div>
          <span>Signal conditions now</span>
          <p>A trade is queued only when the stretch has occurred and all confirmation checks align.</p>
        </div>
        <span className="last-signal">Last signal {formatDateTime(latestSignal.timestamp)}</span>
      </div>
      <div className="condition-grid">
        <ConditionCard
          label="SOXL stretch"
          value={formatNumber(latest.soxl_z_5bar, 2)}
          detail="Trigger: z-score ≤ −1.25"
          passed={stretchTriggered}
          active={latest.oversold_30m}
        />
        <ConditionCard
          label="Bounce"
          value={latest.bounce_confirmed_30m ? 'Confirmed' : 'Waiting'}
          detail="Positive bar plus higher close"
          passed={latest.bounce_confirmed_30m === true}
        />
        <ConditionCard
          label="QQQ regime"
          value={latest.regime_ok_30m ? 'Pass' : 'Blocked'}
          detail={`${formatPercent(latest.qqq_from_open_pct, 2)} from session open`}
          passed={latest.regime_ok_30m === true}
          active={latest.regime_ok_30m === false}
        />
        <ConditionCard
          label="Trade window"
          value={latest.entry_window_ok_30m ? 'Open' : 'Closed'}
          detail={`Bar ${shortText(latest.bar_number, '—')} of 13 · no overnight hold`}
          passed={latest.entry_window_ok_30m === true}
        />
      </div>

      <div className="fast-chart-grid">
        <div className="chart-box feature-chart">
          <div className="console-chart-header">
            <div>
              <h3>SOXL price vs VWAP</h3>
              <p>Completed 30-minute bars from Twelve Data.</p>
            </div>
            <StatusPill tone={hasMarketBars ? 'positive' : 'quiet'}>
              {hasMarketBars ? `${bars.length} bars` : 'Waiting'}
            </StatusPill>
          </div>
          {hasMarketBars ? (
            <ResponsiveContainer width="100%" height={310}>
              <LineChart data={bars} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(185, 206, 255, 0.13)" vertical={false} />
                <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} minTickGap={24} tickFormatter={formatClock} />
                <YAxis tick={{ fontSize: 11 }} width={56} domain={['dataMin - 2', 'dataMax + 2']} tickFormatter={(value) => `$${Math.round(value)}`} />
                <Tooltip labelFormatter={formatDateTime} formatter={(value, name) => [formatPrice(value), name]} />
                <Line type="monotone" dataKey="soxl_close" name="SOXL" stroke="#a78bfa" strokeWidth={3} dot={false} activeDot={{ r: 5 }} />
                <Line type="monotone" dataKey="soxl_vwap" name="VWAP" stroke="#22d3ee" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="Waiting for completed market bars" />
          )}
        </div>

        <div className="chart-box feature-chart equity-chart">
          <div className="console-chart-header">
            <div>
              <h3>30-minute paper equity</h3>
              <p>Marked account value after every processed bar.</p>
            </div>
            <StatusPill tone={state.in_position ? 'warning' : 'accent'}>{paperStatus}</StatusPill>
          </div>
          {equity.length ? (
            <ResponsiveContainer width="100%" height={310}>
              <LineChart data={equity} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(185, 206, 255, 0.13)" vertical={false} />
                <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} minTickGap={24} tickFormatter={formatClock} />
                <YAxis tick={{ fontSize: 11 }} width={68} domain={['auto', 'auto']} tickFormatter={(value) => `$${Math.round(value)}`} />
                <Tooltip labelFormatter={formatDateTime} formatter={(value) => [formatCurrency(value), 'Marked equity']} />
                <ReferenceLine y={summary.starting_capital || 10000} stroke="rgba(255,255,255,.28)" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="marked_equity" name="Equity" stroke="#34d399" strokeWidth={3} dot={false} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="Forward account is building its first observations" />
          )}
        </div>
      </div>

      <div className="execution-note">
        <div>
          <span>Execution model</span>
          <strong>Next 30m open · 50% sizing · 0.10% slippage each way · 3-bar hold</strong>
        </div>
        <p>No real orders are placed. The strategy cannot carry a position overnight.</p>
      </div>

      <div className="activity-tables">
        <DataTable
          title="Completed round trips"
          rows={trades.slice(-8).reverse()}
          columns={[
            ['entry_timestamp', 'BUY time'],
            ['entry_price', 'BUY price'],
            ['exit_timestamp', 'SELL time'],
            ['exit_price', 'SELL price'],
            ['shares', 'Qty'],
            ['position_return', 'Return'],
            ['realized_pnl', 'P&L'],
          ]}
          formatters={{
            entry_timestamp: formatDateTime,
            entry_price: formatPrice,
            exit_timestamp: formatDateTime,
            exit_price: formatPrice,
            shares: (value) => `${formatNumber(value, 3)} sh`,
            position_return: (value) => formatPercent(value, 2),
            realized_pnl: formatCurrency,
          }}
          emptyText="No 30-minute trades have closed yet."
        />
      </div>
    </section>
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
          <strong>{formatPrice(latest.soxl_close || latestMarket.close)}</strong>
        </div>
        <div>
          <span>Market Date</span>
          <strong>{formatDate(latest.market_date || state.last_processed_market_date || latestMarket.date)}</strong>
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
    <section className="strategy-section strategy-section-slow" id="slow-strategy">
      <div className="strategy-kicker-row">
        <div>
          <p className="strategy-kicker strategy-kicker-slow"><span>02</span> Slow strategy</p>
          <h2>Daily oversold recovery paper trader</h2>
          <p className="strategy-summary">
            Waits for an unusually weak five-day SOXL move, confirms the broader QQQ
            trend is healthy, then holds the recovery trade for four sessions.
          </p>
        </div>
        <StatusPill tone={state.in_position ? 'warning' : state.pending_entry ? 'accent' : 'quiet'}>
          {state.in_position ? 'In position' : state.pending_entry ? 'Entry queued' : 'Flat · daily close'}
        </StatusPill>
      </div>

      <div className="strategy-rules strategy-rules-slow">
        <StrategyStep number="1" title="Daily stretch" text="SOXL 5-day z-score falls below −1.50." tone="slow" />
        <StrategyStep number="2" title="Fresh episode" text="Act only on the first day of a new oversold episode." tone="slow" />
        <StrategyStep number="3" title="Trend filter" text="QQQ must remain above its 50-day moving average." tone="slow" />
        <StrategyStep number="4" title="Four-day trade" text="Enter next open with 50%; exit at the day-four close." tone="slow" />
      </div>

      <div className="slow-console">
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
              <div><span>SOXL close</span><strong>{formatPrice(latest.soxl_close)}</strong></div>
              <div><span>QQQ close</span><strong>{formatPrice(latest.qqq_close)}</strong></div>
              <div><span>QQQ MA50</span><strong>{formatPrice(latest.qqq_ma50)}</strong></div>
              <div><span>Signal date</span><strong>{formatDate(state.signal_date)}</strong></div>
            </div>
          </div>

          <div className="side-card">
            <h3>Position</h3>
            <div className="side-facts">
              <div><span>Status</span><strong>{state.in_position ? 'Open' : state.pending_entry ? 'Pending' : 'Flat'}</strong></div>
              <div><span>Entry</span><strong>{formatDate(state.entry_date)}</strong></div>
              <div><span>Entry price</span><strong>{formatPrice(state.entry_price)}</strong></div>
              <div><span>Days held</span><strong>{shortText(state.days_held, '0')}</strong></div>
            </div>
          </div>
        </aside>
      </div>
      </div>
    </section>
  )
}

// Retained as an opt-in local research view; the main dashboard uses FastStrategyPanel.
export function IntradayPanel({ dashboard }) {
  const intraday = dashboard.intraday || {}
  const isCloudLive = String(intraday.mode || '').includes('cloud_live')
  const latest = intraday.latest || {}
  const thirtyMinute = intraday.thirty_minute || {}
  const thirtyMinutePaper = thirtyMinute.paper || {}
  const paper30mSummary = thirtyMinutePaper.summary || {}
  const paper30mState = thirtyMinutePaper.state || {}
  const paper30mEquity = thirtyMinutePaper.equity_curve || []
  const paper30mStatus = paper30mState.in_position
    ? 'In Position'
    : paper30mState.pending_entry
      ? 'Entry Queued'
      : thirtyMinutePaper.active
        ? 'Flat'
        : 'Inactive'
  const overnightPaper = intraday.overnight_rebound_paper || {}
  const overnightSummary = overnightPaper.summary || {}
  const overnightState = overnightPaper.state || {}
  const latest30m = thirtyMinute.latest || {}
  const latest30mSignal = thirtyMinute.latest_signal || {}
  const challengerLive = thirtyMinute.adaptive_challenger || {}
  const latestChallenger = challengerLive.latest || {}
  const backtest = thirtyMinute.backtest || {}
  const backtestSummary = backtest.summary || {}
  const best30m = backtest.best || {}
  const validated30m = backtest.validated || {}
  const challenger = backtest.challenger || {}
  const challengerSummary = challenger.summary || {}
  const challengerValidation = challenger.validation || {}
  const robustness = backtest.robustness || []
  const causalAdaptive = robustness.find(
    (row) => row.strategy_version === 'adaptive_30m_research_v1'
      && row.segment === 'full'
      && row.entry_execution === 'next_bar_open'
      && Number(row.slippage) === 0.001,
  ) || {}
  const stressGuard = robustness.find(
    (row) => row.strategy_version === 'fast_30m_stress_guard_v5_research'
      && row.segment === 'full'
      && row.entry_execution === 'next_bar_open'
      && Number(row.slippage) === 0.001,
  ) || {}
  const dailyShockLatest = backtest.daily_shock_latest || {}
  const hasBacktest = Boolean(backtestSummary.period_end)
  const hasChallenger = Boolean(challengerSummary.period_end)
  const bars = intraday.bars || []
  const watchState = shortText(latest.watch_state, 'Not Running')
  const shadowAction = shortText(latest30m.shadow_action, 'No 30m Data')
  const signalCount30m = Number(thirtyMinute.signal_count || 0)
  const latestWarning = shortText(latest.data_warning, '')
  const hasBars = bars.length > 0

  return (
    <Section
      title={isCloudLive ? 'Live 30-Minute Monitor' : 'Local Intraday Monitor'}
      subtitle={
        isCloudLive
          ? 'Cloud-hosted SOXL/QQQ monitoring from completed Twelve Data bars. This remains a shadow strategy and does not place trades.'
          : 'Separate SOXL/QQQ watch lane for local intraday observation. It logs only; the daily paper strategy is still the official decision system.'
      }
      action={<StatusPill tone={statusTone(watchState)}>{watchState}</StatusPill>}
    >
      <div className="intraday-layout">
        <div className="chart-box intraday-chart">
          <div className="console-chart-header">
            <div>
              <h2>SOXL Today</h2>
              <p>{isCloudLive ? 'Latest completed cloud 30-minute bars with VWAP context.' : 'Latest local 5-minute bars with VWAP context.'}</p>
            </div>
            <StatusPill tone={latestWarning ? 'warning' : hasBars ? 'positive' : 'quiet'}>
              {latestWarning ? 'Data Warning' : hasBars ? (isCloudLive ? 'Cloud Feed' : 'Local Feed') : 'Idle'}
            </StatusPill>
          </div>
          {hasBars ? (
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={bars} margin={{ top: 12, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(226, 232, 240, 0.14)" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  tick={{ fontSize: 12 }}
                  minTickGap={24}
                  tickFormatter={formatClock}
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  width={58}
                  domain={['dataMin - 2', 'dataMax + 2']}
                  tickFormatter={(value) => `$${Math.round(value)}`}
                />
                <Tooltip
                  labelFormatter={(value) => formatDateTime(value)}
                  formatter={(value, name) => [
                    name.includes('pct') ? formatPercent(value, 2) : formatPrice(value),
                    name,
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="soxl_close"
                  name="SOXL last"
                  stroke="#dbeafe"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="soxl_vwap"
                  name="SOXL VWAP"
                  stroke="#67d7f0"
                  strokeWidth={1.8}
                  strokeDasharray="5 5"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              title="Intraday monitor not running"
              text={isCloudLive ? 'The cloud feed has not returned a completed bar yet.' : 'Run python3 -m intraday.monitor --loop --sleep-seconds 300 from the repo root.'}
            />
          )}
        </div>

        <aside className="intraday-side">
          <div className={`command-panel command-${statusTone(watchState)}`}>
            <span>Watch State</span>
            <strong>{watchState}</strong>
            <p>{shortText(latest.reason, 'Start the local intraday monitor to populate this panel.')}</p>
          </div>

          <div className="side-card">
            <h3>Intraday Facts</h3>
            <div className="side-facts">
              <div><span>Market date</span><strong>{formatDate(latest.market_date)}</strong></div>
              <div><span>Latest bar</span><strong>{formatClock(latest.timestamp)}</strong></div>
              <div><span>Bars observed</span><strong>{shortText(latest.bars_observed, '0')}</strong></div>
              <div><span>QQQ from open</span><strong>{formatPercent(latest.qqq_from_open_pct, 2)}</strong></div>
            </div>
          </div>

          <div className="side-card">
            <h3>30-Min Shadow Fast Trader</h3>
            <div className="side-facts">
              <div><span>Action</span><strong>{shadowAction}</strong></div>
              <div><span>Signals today</span><strong>{signalCount30m}</strong></div>
              <div><span>Last signal</span><strong>{formatClock(latest30mSignal.timestamp)}</strong></div>
              <div><span>Window</span><strong>{formatClock(latest30m.timestamp)}</strong></div>
              <div><span>SOXL 5-bar z</span><strong>{formatNumber(latest30m.soxl_z_5bar, 3)}</strong></div>
              <div><span>Regime</span><strong>{latest30m.regime_ok_30m ? 'OK' : 'Blocked'}</strong></div>
              <div><span>Backtest ret</span><strong>{hasBacktest ? formatPercent(backtestSummary.total_return, 2) : 'n/a'}</strong></div>
              <div><span>Backtest trades</span><strong>{hasBacktest ? shortText(backtestSummary.trades, '0') : 'n/a'}</strong></div>
              <div><span>Adaptive shadow</span><strong>{shortText(latestChallenger.shadow_action, 'No data')}</strong></div>
              <div><span>Adaptive signals</span><strong>{challengerLive.signal_count || 0}</strong></div>
            </div>
          </div>

          <div className="side-card">
            <h3>{isCloudLive ? 'Cloud Data' : 'Local Files'}</h3>
            <div className="side-facts">
              <div><span>Bars CSV</span><strong>{intraday.files?.bars?.rows ?? 0} rows</strong></div>
              <div><span>Snapshots CSV</span><strong>{intraday.files?.snapshots?.rows ?? 0} rows</strong></div>
              <div><span>30m CSV</span><strong>{intraday.files?.thirty_minute?.rows ?? 0} rows</strong></div>
              <div><span>30m Backtest</span><strong>{intraday.files?.thirty_minute_backtest?.rows ?? 0} rows</strong></div>
              <div><span>Mode</span><strong>{shortText(intraday.mode, 'local')}</strong></div>
            </div>
          </div>
        </aside>
      </div>

      <div className="metric-grid intraday-metrics">
        <MetricCard
          label="SOXL Last"
          value={formatPrice(latest.soxl_last)}
          detail={`VWAP ${formatPrice(latest.soxl_vwap)}`}
          tone="accent"
        />
        <MetricCard
          label="From Open"
          value={formatPercent(latest.soxl_from_open_pct, 2)}
          detail={`Vs VWAP ${formatPercent(latest.soxl_vs_vwap_pct, 2)}`}
          tone={signedTone(latest.soxl_from_open_pct)}
        />
        <MetricCard
          label="Session Range"
          value={formatPercent(latest.soxl_range_pct, 2)}
          detail={`High ${formatPrice(latest.soxl_session_high)} / Low ${formatPrice(latest.soxl_session_low)}`}
          tone={Number(latest.soxl_range_pct) >= 0.10 ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="From High"
          value={formatPercent(latest.soxl_from_high_pct, 2)}
          detail={`From low ${formatPercent(latest.soxl_from_low_pct, 2)}`}
          tone={Number(latest.soxl_from_high_pct) <= -0.07 ? 'warning' : 'quiet'}
        />
      </div>

      <div className="metric-grid intraday-metrics">
        <MetricCard
          label="30m Shadow Action"
          value={shadowAction}
          detail={`${signalCount30m} signal${signalCount30m === 1 ? '' : 's'} today. Last ${formatClock(latest30mSignal.timestamp)}.`}
          tone={statusTone(shadowAction)}
        />
        <MetricCard
          label="30m SOXL Close"
          value={formatPrice(latest30m.soxl_close)}
          detail={`30m return ${formatPercent(latest30m.soxl_return_30m_pct, 2)}`}
          tone={signedTone(latest30m.soxl_return_30m_pct)}
        />
        <MetricCard
          label="30m Z-Score"
          value={formatNumber(latest30m.soxl_z_5bar, 3)}
          detail={`Last signal z ${formatNumber(latest30mSignal.soxl_z_5bar, 3)}`}
          tone={Number(latest30m.soxl_z_5bar) <= -1.25 ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="30m QQQ Regime"
          value={latest30m.regime_ok_30m ? 'OK' : 'Blocked'}
          detail={`QQQ from open ${formatPercent(latest30m.qqq_from_open_pct, 2)}`}
          tone={latest30m.regime_ok_30m ? 'positive' : 'warning'}
        />
      </div>

      <div className="console-chart-header">
        <div>
          <h2>30-Minute Forward Paper Account</h2>
          <p>$10,000 starting equity with causal next-bar-open fills, costs, drawdown, and trade accounting.</p>
        </div>
        <StatusPill tone={paper30mState.in_position || paper30mState.pending_entry ? 'warning' : thirtyMinutePaper.active ? 'positive' : 'quiet'}>
          {paper30mStatus}
        </StatusPill>
      </div>
      <div className="notice notice-warning">
        {shortText(thirtyMinutePaper.disclosure, 'Forward paper trading is not active.')}
      </div>
      <div className="metric-grid intraday-metrics">
        <MetricCard
          label="30m Paper Equity"
          value={formatCurrency(paper30mSummary.marked_equity)}
          detail={`Total return ${formatPercent(paper30mSummary.total_return, 2)}`}
          tone={signedTone(paper30mSummary.total_return)}
        />
        <MetricCard
          label="Realized P&L"
          value={formatCurrency(paper30mSummary.realized_pnl)}
          detail={`Unrealized ${formatCurrency(paper30mSummary.unrealized_pnl)}`}
          tone={signedTone(paper30mSummary.realized_pnl)}
        />
        <MetricCard
          label="Account State"
          value={paper30mStatus}
          detail={`Last action ${shortText(paper30mSummary.last_action, 'None')}`}
          tone={paper30mState.in_position || paper30mState.pending_entry ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="Position Return"
          value={formatPercent(paper30mSummary.current_position_return, 2)}
          detail={`Exposure ${formatPercent(paper30mSummary.exposure, 1)}`}
          tone={signedTone(paper30mSummary.current_position_return)}
        />
        <MetricCard
          label="Closed Trades"
          value={paper30mSummary.closed_trades ?? 0}
          detail={`Win rate ${formatPercent(paper30mSummary.win_rate, 1)}`}
          tone="quiet"
        />
        <MetricCard
          label="Average Trade"
          value={formatPercent(paper30mSummary.avg_position_return, 2)}
          detail={`Best ${formatPercent(paper30mSummary.best_trade, 2)} / worst ${formatPercent(paper30mSummary.worst_trade, 2)}`}
          tone={signedTone(paper30mSummary.avg_position_return)}
        />
        <MetricCard
          label="Max Drawdown"
          value={formatPercent(paper30mSummary.max_drawdown, 2)}
          detail={`Profit factor ${formatNumber(paper30mSummary.profit_factor, 2)}`}
          tone={Number(paper30mSummary.max_drawdown) < -0.03 ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="Execution Model"
          value="Next 30m Open"
          detail={`${formatPercent(paper30mSummary.position_fraction, 0)} size · ${formatPercent(paper30mSummary.slippage, 2)} slip each way · ${paper30mSummary.hold_bars ?? 3} bars`}
          tone="accent"
        />
      </div>
      <div className="chart-box">
        <div className="console-chart-header">
          <div>
            <h2>30m Forward Equity</h2>
            <p>Marked equity from forward-only cloud paper decisions.</p>
          </div>
        </div>
        {paper30mEquity.length ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={paper30mEquity} margin={{ top: 12, right: 20, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(226, 232, 240, 0.14)" vertical={false} />
              <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} minTickGap={24} tickFormatter={formatClock} />
              <YAxis tick={{ fontSize: 12 }} width={72} domain={['auto', 'auto']} tickFormatter={(value) => `$${Math.round(value)}`} />
              <Tooltip labelFormatter={formatDateTime} formatter={(value) => [formatCurrency(value), 'Marked equity']} />
              <Line type="monotone" dataKey="marked_equity" stroke="#67d7f0" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState title="Paper account not active" text="Forward equity begins at activation." />
        )}
      </div>
      <div className="two-column">
        <DataTable
          title="30m Paper Decisions"
          rows={(thirtyMinutePaper.decisions || []).slice(-10).reverse()}
          columns={[
            ['timestamp', 'Time'],
            ['action', 'Action'],
            ['soxl_close', 'SOXL'],
            ['paper_marked_equity', 'Equity'],
          ]}
          formatters={{
            timestamp: formatDateTime,
            soxl_close: formatPrice,
            paper_marked_equity: formatCurrency,
          }}
          emptyText="No forward paper decisions yet."
        />
        <DataTable
          title="30m Closed Paper Trades"
          rows={(thirtyMinutePaper.trades || []).slice(-10).reverse()}
          columns={[
            ['entry_timestamp', 'Entry'],
            ['exit_timestamp', 'Exit'],
            ['position_return', 'Position'],
            ['realized_pnl', 'P&L'],
          ]}
          formatters={{
            entry_timestamp: formatDateTime,
            exit_timestamp: formatDateTime,
            position_return: (value) => formatPercent(value, 2),
            realized_pnl: formatCurrency,
          }}
          emptyText="No 30-minute paper trades have closed."
        />
      </div>

      <div className="console-chart-header">
        <div>
          <h2>Overnight Rebound Paper Account</h2>
          <p>Buy near the close after a 5% selloff; queue a paper exit for the next open.</p>
        </div>
        <StatusPill tone={overnightSummary.in_position ? 'warning' : 'positive'}>
          {overnightSummary.in_position ? 'Overnight Position' : 'Flat'}
        </StatusPill>
      </div>
      <div className="notice notice-warning">
        {shortText(overnightPaper.disclosure, 'Historical rows are explicitly labeled simulated backfill.')}
      </div>
      <div className="metric-grid intraday-metrics">
        <MetricCard
          label="Overnight Paper Equity"
          value={formatCurrency(overnightSummary.marked_equity)}
          detail={`Return ${formatPercent(overnightSummary.total_return, 2)}`}
          tone={signedTone(overnightSummary.total_return)}
        />
        <MetricCard
          label="Overnight Account State"
          value={overnightSummary.in_position ? 'In position' : 'Flat'}
          detail={overnightState.entry_market_date ? `Entered ${formatDate(overnightState.entry_market_date)}` : 'Waiting for a 3:30 p.m. signal'}
          tone={overnightSummary.in_position ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="Overnight Closed Trades"
          value={overnightSummary.closed_trades ?? 0}
          detail={`Win rate ${formatPercent(overnightSummary.win_rate, 1)}`}
          tone="quiet"
        />
        <MetricCard
          label="Evidence Mix"
          value={`${overnightSummary.forward_events || 0} live`}
          detail={`${overnightSummary.backfilled_events || 0} simulated backfill events`}
          tone="accent"
        />
      </div>
      <div className="two-column">
        <DataTable
          title="Overnight Paper Decisions"
          rows={(overnightPaper.decisions || []).slice(-8).reverse()}
          columns={[
            ['market_date', 'Date'],
            ['action', 'Action'],
            ['signal_from_open_pct', 'From Open'],
            ['provenance', 'Evidence'],
          ]}
          formatters={{
            market_date: formatDate,
            signal_from_open_pct: (value) => formatPercent(value, 2),
          }}
          emptyText="No overnight paper decisions have been logged."
        />
        <DataTable
          title="Overnight Paper Trades"
          rows={(overnightPaper.trades || []).slice(-8).reverse()}
          columns={[
            ['entry_market_date', 'Entry'],
            ['exit_market_date', 'Exit'],
            ['position_return', 'Position'],
            ['account_return', 'Account'],
            ['provenance', 'Evidence'],
          ]}
          formatters={{
            entry_market_date: formatDate,
            exit_market_date: formatDate,
            position_return: (value) => formatPercent(value, 2),
            account_return: (value) => formatPercent(value, 2),
          }}
          emptyText="No overnight paper trades have closed."
        />
      </div>

      <div className="metric-grid intraday-metrics">
        <MetricCard
          label="30m Backtest Return"
          value={hasBacktest ? formatPercent(backtestSummary.total_return, 2) : 'n/a'}
          detail={
            hasBacktest
              ? `${backtestSummary.trades || 0} trades through ${formatDate(backtestSummary.period_end)}`
              : 'Run python3 -m intraday.monitor --backtest --backtest-period 90d'
          }
          tone={hasBacktest ? signedTone(backtestSummary.total_return) : 'quiet'}
        />
        <MetricCard
          label="30m Backtest Win Rate"
          value={hasBacktest ? formatPercent(backtestSummary.win_rate, 1) : 'n/a'}
          detail={`Avg trade ${formatPercent(backtestSummary.avg_position_return, 2)}`}
          tone="quiet"
        />
        <MetricCard
          label="30m Max Drawdown"
          value={hasBacktest ? formatPercent(backtestSummary.max_drawdown, 2) : 'n/a'}
          detail={`Final equity ${formatCurrency(backtestSummary.final_equity)}`}
          tone={Number(backtestSummary.max_drawdown) < -0.03 ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="Best Small Scan"
          value={
            best30m.z_threshold !== undefined
              ? shortText(best30m.entry_style, 'n/a')
              : 'n/a'
          }
          detail={
            best30m.hold_bars !== undefined
              ? `z ${formatNumber(best30m.z_threshold, 2)}, hold ${best30m.hold_bars}, wait ${shortText(best30m.bounce_wait_bars, '0')}, return ${formatPercent(best30m.total_return, 2)}`
              : 'Parameter scan appears after a backtest.'
          }
          tone={signedTone(best30m.total_return)}
        />
        <MetricCard
          label="Validated Pick"
          value={shortText(validated30m.entry_style, 'n/a')}
          detail={
            validated30m.test_return !== undefined
              ? `${validated30m.passes_validation ? 'Passed' : 'Failed'} validation. Test ${formatPercent(validated30m.test_return, 2)}, ${validated30m.test_trades || 0} trades`
              : 'Run the backtest to populate train/test validation.'
          }
          tone={validated30m.passes_validation ? signedTone(validated30m.test_return) : 'warning'}
        />
        <MetricCard
          label="Adaptive Research Challenger"
          value={hasChallenger ? formatPercent(challengerSummary.total_return, 2) : 'n/a'}
          detail={
            hasChallenger
              ? `${challengerSummary.trades || 0} trades, ${formatPercent(challengerSummary.win_rate, 1)} win rate`
              : 'Research-only; run the 30m backtest to compare it with v4.'
          }
          tone={hasChallenger ? signedTone(challengerSummary.total_return) : 'quiet'}
        />
        <MetricCard
          label="Challenger Drawdown"
          value={hasChallenger ? formatPercent(challengerSummary.max_drawdown, 2) : 'n/a'}
          detail="Deep-reversion plus trend-pullback lanes; never sent to paper trading."
          tone={Number(challengerSummary.max_drawdown) < -0.05 ? 'warning' : 'quiet'}
        />
        <MetricCard
          label="Challenger Time Split"
          value={challengerValidation.passes_chronological_check ? 'Passed' : 'Not passed'}
          detail={
            challengerValidation.test_return !== undefined
              ? `Validation ${formatPercent(challengerValidation.validation_return, 2)} / test ${formatPercent(challengerValidation.test_return, 2)}`
              : 'Requires chronological train, validation, and test output.'
          }
          tone={challengerValidation.passes_chronological_check ? 'positive' : 'warning'}
        />
        <MetricCard
          label="Causal Adaptive Return"
          value={causalAdaptive.total_return !== undefined ? formatPercent(causalAdaptive.total_return, 2) : 'n/a'}
          detail="Next-bar-open fills with 0.1% slippage each way."
          tone={signedTone(causalAdaptive.total_return)}
        />
        <MetricCard
          label="V5 Stress Guard"
          value={stressGuard.total_return !== undefined ? formatPercent(stressGuard.total_return, 2) : 'n/a'}
          detail={`${stressGuard.trades || 0} trades; one entry per session; research only.`}
          tone={signedTone(stressGuard.total_return)}
        />
        <MetricCard
          label="Latest Daily Shock"
          value={dailyShockLatest.return_5d !== undefined ? formatPercent(dailyShockLatest.return_5d, 2) : 'n/a'}
          detail={`20-day drawdown ${formatPercent(dailyShockLatest.drawdown_20d, 2)} through ${formatDate(dailyShockLatest.market_date)}`}
          tone="warning"
        />
      </div>

      <div className="three-column intraday-backtest-tables">
        <DataTable
          title="30m Recent Backtest Trades"
          rows={(backtest.recent_trades || []).slice(-6).reverse()}
          columns={[
            ['entry_timestamp', 'Entry'],
            ['exit_timestamp', 'Exit'],
            ['position_return', 'Return'],
          ]}
          formatters={{
            entry_timestamp: formatClock,
            exit_timestamp: formatClock,
            position_return: (value) => formatPercent(value, 2),
          }}
          emptyText="No 30m backtest trades yet."
        />
        <DataTable
          title="30m Parameter Scan"
          rows={backtest.top_parameters || []}
          columns={[
            ['entry_style', 'Entry'],
            ['z_threshold', 'Z'],
            ['hold_bars', 'Hold'],
            ['bounce_wait_bars', 'Wait'],
            ['total_return', 'Return'],
            ['trades', 'Trades'],
          ]}
          formatters={{
            z_threshold: (value) => formatNumber(value, 2),
            total_return: (value) => formatPercent(value, 2),
          }}
          emptyText="Run the 30m backtest to populate the scan."
        />
        <DataTable
          title="30m Backtest Summary"
          rows={hasBacktest ? [backtestSummary] : []}
          columns={[
            ['entry_style', 'Entry'],
            ['period_start', 'Start'],
            ['period_end', 'End'],
            ['bars', 'Bars'],
            ['trades', 'Trades'],
          ]}
          formatters={{
            period_start: formatDate,
            period_end: formatDate,
          }}
          emptyText="No 30m backtest summary yet."
        />
        <DataTable
          title="30m Validation"
          rows={backtest.validation || []}
          columns={[
            ['entry_style', 'Entry'],
            ['z_threshold', 'Z'],
            ['passes_validation', 'Pass'],
            ['test_return', 'Test Ret'],
            ['test_trades', 'Trades'],
          ]}
          formatters={{
            z_threshold: (value) => formatNumber(value, 2),
            passes_validation: (value) => (value ? 'Yes' : 'No'),
            test_return: (value) => formatPercent(value, 2),
          }}
          emptyText="Run the 30m backtest to populate validation."
        />
        <DataTable
          title="Adaptive Challenger Trades"
          rows={(challenger.recent_trades || []).slice(-6).reverse()}
          columns={[
            ['entry_timestamp', 'Entry'],
            ['exit_timestamp', 'Exit'],
            ['position_return', 'Return'],
          ]}
          formatters={{
            entry_timestamp: formatClock,
            exit_timestamp: formatClock,
            position_return: (value) => formatPercent(value, 2),
          }}
          emptyText="No adaptive challenger backtest trades yet."
        />
        <DataTable
          title="Execution & Cost Robustness"
          rows={robustness.filter(
            (row) => row.segment === 'full' && row.entry_execution === 'next_bar_open',
          )}
          columns={[
            ['strategy_version', 'Version'],
            ['slippage', 'Slip'],
            ['total_return', 'Return'],
            ['max_drawdown', 'Max DD'],
            ['trades', 'Trades'],
          ]}
          formatters={{
            slippage: (value) => formatPercent(value, 2),
            total_return: (value) => formatPercent(value, 2),
            max_drawdown: (value) => formatPercent(value, 2),
          }}
          emptyText="Run the 30m backtest to populate causal robustness."
        />
        <DataTable
          title="Modern Daily Shock Context"
          rows={backtest.daily_shock_context || []}
          columns={[
            ['shock_threshold_5d', '5D Shock'],
            ['forward_sessions', 'Forward'],
            ['events', 'Events'],
            ['median_forward_return', 'Median'],
            ['positive_rate', 'Positive'],
            ['worst_forward_return', 'Worst'],
          ]}
          formatters={{
            shock_threshold_5d: (value) => formatPercent(value, 0),
            forward_sessions: (value) => `${value}d`,
            median_forward_return: (value) => formatPercent(value, 2),
            positive_rate: (value) => formatPercent(value, 1),
            worst_forward_return: (value) => formatPercent(value, 2),
          }}
          emptyText="No daily shock context is available."
        />
      </div>

      {latestWarning ? (
        <div className="notice notice-warning">Latest intraday data warning: {latestWarning}</div>
      ) : null}
    </Section>
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
      title="Daily strategy price and signals"
      subtitle="Where the slower strategy historically signaled, entered, and exited on adjusted SOXL prices."
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
                    name === 'position_return' ? formatPercent(value, 2) : formatPrice(value),
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
            <strong>{formatPrice(latest.close)}</strong>
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
      title="Daily strategy historical performance"
      subtitle="Backtest evidence for context only. Forward paper results above remain the real scorecard."
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
      title="Daily strategy activity"
      subtitle="Recent slow-strategy decisions, signals, and closed paper trades."
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
            ['data_warning', 'Warning'],
          ]}
          formatters={{
            soxl_z_score: (value) => formatNumber(value, 3),
            buy_signal: (value) => (value ? 'Yes' : 'No'),
            data_warning: (value) => shortText(value, 'None'),
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
  const liveApi = dashboard.live_api || {}
  const liveRefresh = liveApi.latest_refresh || {}
  const exportInfo = dashboard.static_export || {}
  const paperBotWorkflow = exportInfo.paper_bot_workflow || {}
  const latest = dashboard.latest_daily_log || {}
  const latestWarning = shortText(latest.data_warning, '')
  const paperBotStatus = paperBotWorkflow.conclusion || paperBotWorkflow.status
  const paperBotTone = statusTone(paperBotStatus)
  const fastLatest = dashboard.intraday?.thirty_minute?.latest || {}

  return (
    <Section
      title="System status"
      subtitle="A compact freshness check for the two data lanes."
    >
      <div className="health-grid">
        <div className={`health-row health-row-${liveApi.connected ? 'positive' : 'warning'}`}>
          <span>30-minute feed</span>
          <strong>{liveApi.connected ? 'Connected' : 'Unavailable'}</strong>
          <em>{shortText(liveApi.error, liveApi.connected ? 'Cloudflare Worker online' : 'Live API not configured')}</em>
        </div>
        <div className="health-row health-row-fast">
          <span>Latest 30-minute bar</span>
          <strong>{formatDate(fastLatest.market_date)}</strong>
          <em>{formatDateTime(liveRefresh.latest_bar_timestamp || fastLatest.timestamp)}</em>
        </div>
        <div className={`health-row health-row-${paperBotStatus ? paperBotTone : 'quiet'}`}>
          <span>Daily paper bot</span>
          <strong>{shortText(paperBotStatus, 'Local data')}</strong>
          <em>{formatDate(latest.market_date)}</em>
        </div>
        <div className="health-row health-row-accent">
          <span>Dashboard source</span>
          <strong>{exportInfo.generated_at_utc ? 'Cloudflare Pages' : 'Local API'}</strong>
          <em>{exportInfo.generated_at_utc ? formatDateTime(exportInfo.generated_at_utc) : 'FastAPI response'}</em>
        </div>
      </div>
      {latestWarning ? (
        <div className="notice notice-warning">Latest data warning: {latestWarning}</div>
      ) : null}
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
      const response = await fetch(DASHBOARD_URL, { cache: 'no-store' })
      if (!response.ok) {
        throw new Error(`Dashboard source returned ${response.status}`)
      }
      const basePayload = await response.json()
      let livePayload = null
      let liveError = ''
      if (LIVE_DASHBOARD_URL) {
        try {
          const liveResponse = await fetch(LIVE_DASHBOARD_URL, { cache: 'no-store' })
          if (!liveResponse.ok) {
            throw new Error(`Live API returned ${liveResponse.status}`)
          }
          livePayload = await liveResponse.json()
        } catch (requestError) {
          liveError = requestError.message || 'Unable to load live 30-minute data.'
        }
      }
      setDashboard(mergeLiveDashboard(basePayload, livePayload, liveError))
      setRefreshedAt(new Date().toLocaleTimeString())
    } catch (loadError) {
      setError(loadError.message || 'Unable to load dashboard.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const initialTimer = window.setTimeout(loadDashboard, 0)
    const refreshTimer = LIVE_DASHBOARD_URL
      ? window.setInterval(loadDashboard, LIVE_REFRESH_MS)
      : null
    return () => {
      window.clearTimeout(initialTimer)
      if (refreshTimer) window.clearInterval(refreshTimer)
    }
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
        <FastStrategyPanel dashboard={dashboard} />
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
