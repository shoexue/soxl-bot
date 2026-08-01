export const STRATEGY = Object.freeze({
  version: "fast_30m_validated_v4",
  zWindow: 5,
  zThreshold: -1.25,
  qqqFloorPct: -0.01,
  holdBars: 3,
  bounceWaitBars: 2,
  sessionBars: 13,
});

const EASTERN_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const EASTERN_SCHEDULE_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function finiteNumber(value, fieldName) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error(`Invalid ${fieldName}: ${value}`);
  }
  return number;
}

function partsRecord(parts) {
  return Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
}

export function normalizeTwelveDataTimestamp(value) {
  const text = String(value ?? "").trim();
  const match = text.match(
    /^(\d{4}-\d{2}-\d{2})[T\s]*(\d{2}):(\d{2}):(\d{2})$/,
  );
  if (!match) {
    throw new Error(`Invalid Twelve Data timestamp: ${text}`);
  }
  return `${match[1]}T${match[2]}:${match[3]}:${match[4]}`;
}

export function easternLocalToUtcIso(localTimestamp) {
  const normalized = normalizeTwelveDataTimestamp(localTimestamp);
  const [datePart, timePart] = normalized.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const [hour, minute, second] = timePart.split(":").map(Number);
  const localAsUtc = Date.UTC(year, month - 1, day, hour, minute, second);

  // Noon/market timestamps are not DST-ambiguous. Two passes also keep this
  // correct across Eastern offset changes without hard-coding -04:00/-05:00.
  let utcMillis = localAsUtc;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const eastern = partsRecord(EASTERN_PARTS.formatToParts(new Date(utcMillis)));
    const easternAsUtc = Date.UTC(
      Number(eastern.year),
      Number(eastern.month) - 1,
      Number(eastern.day),
      Number(eastern.hour),
      Number(eastern.minute),
      Number(eastern.second),
    );
    utcMillis = localAsUtc - (easternAsUtc - utcMillis);
  }
  return new Date(utcMillis).toISOString();
}

function isRegularSessionLocal(localTimestamp) {
  const time = localTimestamp.slice(11, 16);
  return time >= "09:30" && time <= "15:30";
}

export function parseTwelveDataBars(values, symbol, now = new Date()) {
  if (!Array.isArray(values)) {
    throw new Error(`Twelve Data returned no values for ${symbol}`);
  }

  const completedCutoff = now.getTime();
  const rows = values.map((value) => {
    const localDatetime = normalizeTwelveDataTimestamp(value.datetime);
    const timestamp = easternLocalToUtcIso(localDatetime);
    return {
      symbol,
      timestamp,
      local_datetime: localDatetime,
      market_date: localDatetime.slice(0, 10),
      interval: "30min",
      open: finiteNumber(value.open, `${symbol} open`),
      high: finiteNumber(value.high, `${symbol} high`),
      low: finiteNumber(value.low, `${symbol} low`),
      close: finiteNumber(value.close, `${symbol} close`),
      volume: finiteNumber(value.volume ?? 0, `${symbol} volume`),
    };
  });

  return rows
    .filter((row) => isRegularSessionLocal(row.local_datetime))
    .filter(
      (row) =>
        new Date(row.timestamp).getTime() + 30 * 60 * 1000 <= completedCutoff,
    )
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp));
}

export function isMarketRefreshWindow(now) {
  const eastern = partsRecord(
    EASTERN_SCHEDULE_PARTS.formatToParts(now),
  );
  if (eastern.weekday === "Sat" || eastern.weekday === "Sun") {
    return false;
  }
  const minuteOfDay = Number(eastern.hour) * 60 + Number(eastern.minute);
  return minuteOfDay >= 10 * 60 && minuteOfDay <= 16 * 60 + 5;
}

function pctChange(current, base) {
  if (!Number.isFinite(current) || !Number.isFinite(base) || base === 0) {
    return null;
  }
  return current / base - 1;
}

function sampleStandardDeviation(values) {
  if (values.length < 2) return null;
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance =
    values.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    (values.length - 1);
  return Math.sqrt(variance);
}

function rollingZScore(closes) {
  if (closes.length < STRATEGY.zWindow) return null;
  const window = closes.slice(-STRATEGY.zWindow);
  const mean = window.reduce((sum, value) => sum + value, 0) / window.length;
  const standardDeviation = sampleStandardDeviation(window);
  if (!standardDeviation) return null;
  return (window.at(-1) - mean) / standardDeviation;
}

export function buildSignalRows(soxlBars, qqqBars, calculatedAt = new Date()) {
  const qqqByTimestamp = new Map(
    qqqBars.map((bar) => [bar.timestamp, bar]),
  );
  const aligned = [...soxlBars]
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    .flatMap((soxl) => {
      const qqq = qqqByTimestamp.get(soxl.timestamp);
      return qqq ? [{ soxl, qqq }] : [];
    });

  const rows = [];
  const closes = [];
  let currentMarketDate = null;
  let sessionOpen = null;
  let qqqSessionOpen = null;
  let sessionHigh = null;
  let sessionLow = null;
  let cumulativeVolume = 0;
  let cumulativeCloseValue = 0;
  let barNumber = 0;
  let previousClose = null;
  let previousOversold = false;
  let activeEpisode = false;
  let activeMarketDate = null;
  let barsSinceEpisode = 0;

  for (const { soxl, qqq } of aligned) {
    const newSession = soxl.market_date !== currentMarketDate;
    if (newSession) {
      currentMarketDate = soxl.market_date;
      sessionOpen = soxl.open;
      qqqSessionOpen = qqq.open;
      sessionHigh = soxl.high;
      sessionLow = soxl.low;
      cumulativeVolume = 0;
      cumulativeCloseValue = 0;
      barNumber = 0;
    }

    if (activeEpisode && soxl.market_date !== activeMarketDate) {
      activeEpisode = false;
      barsSinceEpisode = 0;
    }

    barNumber += 1;
    sessionHigh = Math.max(sessionHigh, soxl.high);
    sessionLow = Math.min(sessionLow, soxl.low);
    cumulativeVolume += soxl.volume;
    cumulativeCloseValue += soxl.close * soxl.volume;
    const vwap =
      cumulativeVolume > 0 ? cumulativeCloseValue / cumulativeVolume : null;

    closes.push(soxl.close);
    const zScore = rollingZScore(closes);
    const oversold = zScore !== null && zScore <= STRATEGY.zThreshold;
    const episodeStart =
      oversold && (!previousOversold || newSession);
    const qqqFromOpen = pctChange(qqq.close, qqqSessionOpen);
    const regimeOk =
      qqqFromOpen !== null && qqqFromOpen >= STRATEGY.qqqFloorPct;
    const entryWindowOk =
      barNumber + STRATEGY.holdBars <= STRATEGY.sessionBars;
    const soxlReturn = pctChange(soxl.close, soxl.open);

    let barsSinceValue = null;
    let bounceConfirmed = false;
    let shadowSignal = false;

    if (episodeStart) {
      activeEpisode = true;
      activeMarketDate = soxl.market_date;
      barsSinceEpisode = 0;
      barsSinceValue = 0;
    } else if (activeEpisode) {
      barsSinceEpisode += 1;
      barsSinceValue = barsSinceEpisode;
    }

    if (activeEpisode && !episodeStart) {
      const positiveBar = (soxlReturn ?? 0) > 0;
      const higherClose =
        previousClose !== null && soxl.close > previousClose;
      bounceConfirmed =
        barsSinceEpisode <= STRATEGY.bounceWaitBars &&
        positiveBar &&
        higherClose;
      shadowSignal = bounceConfirmed && regimeOk && entryWindowOk;
    }

    let shadowAction = "WAIT";
    let shadowReason = "No completed 30-minute shadow setup.";
    if (shadowSignal) {
      activeEpisode = false;
      shadowAction = "SHADOW_LONG_WATCH";
      shadowReason =
        "30-minute SOXL bounce confirmed after an oversold reset while QQQ held up.";
    } else if (episodeStart && !regimeOk) {
      shadowAction = "REGIME_BLOCKED";
      shadowReason =
        "30-minute SOXL reset fired, but QQQ intraday regime failed.";
    } else if (episodeStart && !entryWindowOk) {
      shadowAction = "TOO_LATE";
      shadowReason =
        "30-minute reset fired too late to complete the same-day hold.";
    } else if (episodeStart) {
      shadowAction = "OVERSOLD_WATCH";
      shadowReason =
        "30-minute SOXL reset started; waiting for a bounce bar.";
    } else if (bounceConfirmed && !regimeOk) {
      shadowAction = "REGIME_BLOCKED";
      shadowReason =
        "SOXL bounced after the reset, but QQQ intraday regime failed.";
    } else if (bounceConfirmed && !entryWindowOk) {
      shadowAction = "TOO_LATE";
      shadowReason =
        "SOXL bounced, but there are not enough same-day bars left.";
    } else if (oversold) {
      shadowAction = "OVERSOLD_WATCH";
      shadowReason = "30-minute SOXL z-score is stretched lower.";
    }

    rows.push({
      timestamp: soxl.timestamp,
      local_datetime: soxl.local_datetime,
      market_date: soxl.market_date,
      interval: "30min",
      strategy_version: STRATEGY.version,
      soxl_open: soxl.open,
      soxl_high: soxl.high,
      soxl_low: soxl.low,
      soxl_close: soxl.close,
      soxl_volume: soxl.volume,
      soxl_vwap: vwap,
      soxl_return_30m_pct: soxlReturn,
      soxl_z_5bar: zScore,
      soxl_vs_vwap_pct: pctChange(soxl.close, vwap),
      soxl_from_open_pct: pctChange(soxl.close, sessionOpen),
      soxl_from_high_pct: pctChange(soxl.close, sessionHigh),
      soxl_from_low_pct: pctChange(soxl.close, sessionLow),
      soxl_session_range_pct: pctChange(sessionHigh, sessionLow),
      soxl_session_high: sessionHigh,
      soxl_session_low: sessionLow,
      bar_number: barNumber,
      qqq_close: qqq.close,
      qqq_return_30m_pct: pctChange(qqq.close, qqq.open),
      qqq_from_open_pct: qqqFromOpen,
      bars_in_window: 1,
      oversold_30m: oversold,
      episode_start_30m: episodeStart,
      bars_since_episode_start_30m: barsSinceValue,
      bounce_confirmed_30m: bounceConfirmed,
      regime_ok_30m: regimeOk,
      entry_window_ok_30m: entryWindowOk,
      shadow_signal: shadowSignal,
      shadow_action: shadowAction,
      shadow_reason: shadowReason,
      calculated_at: calculatedAt.toISOString(),
    });

    if (activeEpisode && barsSinceEpisode >= STRATEGY.bounceWaitBars) {
      activeEpisode = false;
    }
    previousClose = soxl.close;
    previousOversold = oversold;
  }

  return rows;
}
