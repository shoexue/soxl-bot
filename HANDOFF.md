# SOXL FAST MEAN-REVERSION BOT — PROJECT HANDOFF

## 1. ROLE OF THE NEXT BOT

You are continuing an existing quantitative trading research and paper-trading project.

Do not restart the project from scratch.

Do not immediately run broad parameter searches.

Do not optimize parameters just because a recent trade or market move looks unusual.

Your immediate job is to:

1. understand the existing research,
2. preserve reproducibility,
3. update the paper bot to the frozen fast-strategy candidate,
4. improve paper-trading reliability,
5. collect genuinely unseen forward data,
6. teach the user the relevant trading and quantitative concepts as the project progresses.

The user is technically strong and can code, but is relatively new to trading. Explain trading concepts clearly without oversimplifying the programming.

The project is currently transitioning from:

RESEARCH PHASE

to:

PAPER-TRADING / ENGINEERING PHASE

# 2. PROJECT GOAL

The original goal was to build a systematic trading strategy for SOXL.

SOXL is a daily 3x leveraged semiconductor ETF and can make very large daily moves.

The original question was whether to use:

* mean reversion,
* Random Forest / ML,
* or mean reversion with an ML filter.

The project intentionally chose to develop and validate a deterministic mean-reversion strategy first.

ML was postponed because the number of genuinely independent trading events is still too small for a convincing supervised ML model.

The eventual ML direction, if justified later, is:

Use ML as a filter or ranking model on top of a deterministic mean-reversion signal.

Do not currently attempt to predict every daily SOXL return with Random Forest.

# 3. CORE RESEARCH HYPOTHESIS

The current hypothesis is:

When SOXL experiences unusually sharp short-term weakness relative to approximately its previous 5–6 trading days, while QQQ remains in an intermediate-term uptrend, SOXL has historically tended to rebound over approximately the following 4–5 trading sessions.

Conceptually:

SHORT-TERM SOXL SHOCK
+
BROADER TECH UPTREND STILL INTACT
=================================

POTENTIAL SHORT-TERM MEAN-REVERSION TRADE

# 4. CURRENT PRIMARY STRATEGY CANDIDATE

The current strategy candidate to paper trade is:

ASSET:
SOXL

SIGNAL WINDOW:
5 trading days

SIGNAL:
Calculate rolling SOXL z-score:

z = (Close - rolling mean) / rolling standard deviation

using a 5-day rolling window.

ENTRY CONDITION:

1. SOXL 5-day z-score is below -1.50.
2. This is the first day of a new oversold episode.
3. QQQ Close is above its 50-day simple moving average.

EPISODE START LOGIC:

oversold_today == True
AND
oversold_previous_day == False

This prevents entering repeatedly on every day of the same oversold episode.

ENTRY EXECUTION:

Signal is calculated after the daily close.

Enter at the NEXT trading day's OPEN.

Current backtests assumed approximately 0.1% slippage on entry and exit.

POSITION SIZE FOR PAPER TEST:

50% of current paper account equity.

EXIT:

Exit at the CLOSE of holding day 4.

The convention previously used is:

Day 1 = entry day's close
Day 2 = following trading day's close
Day 3 = next close
Day 4 = fourth session's close including the entry session as Day 1

CURRENT STOP:

No simple fixed stop in the frozen paper candidate.

Reason:

Fixed stops at -8%, -10%, -12%, and -15% were tested. They generally damaged the strategy because the strategy intentionally enters during violent weakness and many eventual winners experience substantial adverse movement before recovering.

IMPORTANT:

No fixed stop does not mean risk is solved.

SOXL is leveraged and can gap sharply. Risk is currently controlled mainly through position sizing and paper trading.

Do not interpret historical results as a guarantee of future returns.

# 5. IMPORTANT BENCHMARK STRATEGY

Keep the original slower strategy as a research benchmark.

ORIGINAL STRATEGY:

SOXL 20-day z-score < -1.75
first day of oversold episode
QQQ above 50-day MA
enter next open

EXIT:

-12% stop
+20% target
or maximum 5 trading-day hold

POSITION SIZE:

50%

This strategy had fewer historical trades and lower total portfolio return in the comparison, but a high historical win rate.

Do not delete this strategy from research history.

It is useful as a benchmark against the fast strategy.

# 6. RESEARCH HISTORY

## Phase A — Original mean-reversion research

The project began with a slower SOXL mean-reversion strategy.

The major discovery was that buying SOXL weakness indiscriminately was not enough.

Adding the regime filter:

QQQ Close > QQQ 50-day moving average

materially improved results.

This led to the interpretation:

Buy short-term semiconductor weakness when the broader technology trend remains structurally healthy.

## Phase B — Modern-period focus

The user strongly prefers focusing on the modern semiconductor/AI market environment.

Most research was therefore scoped to approximately:

2021-01-01 onward

with extra earlier data downloaded only to warm up rolling indicators.

Do not silently expand optimization back through SOXL's entire history without discussing the implications.

The user's thesis is that the current AI-driven semiconductor environment may differ structurally from older periods.

However, the next bot should also understand the statistical downside:

Restricting the period creates a smaller sample.

The correct response is not to pretend older history is necessarily useless or necessarily representative. Treat regime relevance and sample size as a research tradeoff.

# 7. FAST-WINDOW DISCOVERY

The user challenged the original 20-day window because SOXL frequently makes extremely large daily moves.

This led to testing shorter signal windows.

Initial fast grid included approximately:

z-score windows:
3, 5, 10, 20

thresholds:
-1.25, -1.50, -1.75, -2.00

holds:
1, 2, 3, 5 trading days

QQQ > MA50 remained fixed.

Entry remained next open.

The important result was:

Short signal windows were promising, but the strongest effect was not necessarily an immediate one-day rebound.

A roughly 5-day signal combined with a several-day hold was much stronger than the simple one-day snapback hypothesis.

# 8. FAST STRATEGY VS ORIGINAL PORTFOLIO TEST

A non-overlapping portfolio comparison was performed.

Approximate results reported:

CURRENT 20D STRATEGY:

Executed trades: 12
$10,000 final value: approximately $14,378
Total return: approximately +43.8%
Max drawdown: approximately -15.5%
Win rate: approximately 75%
Average position return: approximately +6.5%

FAST 5D CANDIDATE AT THAT STAGE:

Executed trades: 32
$10,000 final value: approximately $17,400
Total return: approximately +74.0%
Max drawdown: approximately -16.7%
Win rate: approximately 62.5%
Average position return: approximately +3.76%

Interpretation:

The fast strategy traded more often and produced higher historical portfolio growth with only moderately worse measured drawdown.

This justified further research into the fast strategy family.

# 9. LOCAL ROBUSTNESS AND RETURN-PATH ANALYSIS

A local robustness study was run around short windows.

Windows tested included approximately:

3, 4, 5, 6, 7, 8, 10 days

with multiple feasible z-score thresholds and holding periods.

The important finding was not merely that exactly 5 days worked.

A broader short-window neighborhood around approximately 4–8 days showed promising behavior.

This reduced concern that the entire result came from one isolated parameter combination.

## Return path for 5D z < -1.50

Approximate historical post-entry results:

Day 1:
average +0.26%
win rate 57.1%

Day 2:
average -0.03%
win rate 40.0%

Day 3:
average +2.59%
win rate 57.1%

Day 4:
average +4.94%
median +6.14%
win rate 71.4%
worst final return approximately -10.9%

Day 5:
average +3.87%
median +5.18%
win rate 65.7%
worst final return approximately -20.9%

Day 6:
average +3.10%

Day 7:
average +1.13%

Interpretation:

The historical rebound did not generally appear as a pure next-day snapback.

The return path tended to strengthen around Days 3–5, with Day 4 especially interesting.

This motivated the current Day-4 exit.

# 10. WALK-FORWARD VALIDATION

A walk-forward test was performed.

The idea:

For each test year, choose parameters using only earlier data and then evaluate the selected parameters on the unseen next year.

Approximate folds:

Train 2021–2022 → test 2023
Train 2021–2023 → test 2024
Train 2021–2024 → test 2025
Train 2021–2025 → test 2026 YTD

The short-family search was constrained approximately to:

windows 4–8
thresholds -1.1 through -1.8
holds 3–5

The parameter selection pattern was relatively stable.

Reported selections:

2023 test:
6D, -1.7, hold 5

2024 test:
6D, -1.7, hold 5

2025 test:
6D, -1.7, hold 4

2026 YTD test:
6D, -1.1, hold 4

Combined reported out-of-sample results:

14 trades
average return approximately +3.34%
median return approximately +5.37%
win rate approximately 85.7%
compounded trade sequence approximately +49.5%
best trade approximately +17.8%
worst trade approximately -20.9%
positive test years: 4/4

IMPORTANT LIMITATIONS:

* 14 OOS trades is still a small sample.
* 2026 was partial-year data.
* The broader research process has repeatedly examined the 2021–2026 environment.
* Walk-forward evidence is encouraging, not proof.

# 11. EXECUTION AND DOWNSIDE TEST

A downside analysis tested the fast strategy family with:

No stop
-8% stop
-10% stop
-12% stop
-15% stop

The primary finding:

Simple fixed stops generally reduced performance.

For the approximate 5D / -1.5 / hold-4 candidate:

NO STOP:

35 trades
average position return approximately +4.94%
win rate approximately 71.4%
reported 50%-sized trade-sequence return approximately +128.2%
trade-sequence drawdown approximately -8.6%

-8% STOP:

average position return approximately +3.11%
win rate approximately 57.1%
reported sequence return approximately +65.1%
drawdown approximately -11.7%

-15% STOP:

average position return approximately +3.96%
win rate approximately 68.6%
reported sequence return approximately +91.0%
drawdown approximately -14.5%

Interpretation:

The mean-reversion trade often experiences adverse movement before recovering.

For the 5D candidate, median MAE was approximately -5.7%.

An -8% stop reportedly triggered on 11 of 35 trades and materially reduced performance.

IMPORTANT CAVEAT:

The Step 22 drawdown calculation was based on the sequence of completed trades.

It was NOT a full daily mark-to-market equity curve.

Therefore, do not present the approximately -8.6% number as the true worst intratrade portfolio drawdown.

One historical trade had position-level MAE around -25.3%.

At 50% allocation, that implies a substantial temporary account-level impact.

A proper mark-to-market equity simulation remains useful engineering/research work.

# 12. CURRENT PAPER BOT STATUS

An initial paper bot was already created and successfully run.

However, it currently implements the OLD 20-day strategy.

Initial paper bot logic:

20-day SOXL z-score
threshold -1.75
QQQ > MA50
next-open entry
-12% stop
+20% target
5-day maximum hold
50% allocation

Initial paper account:

$10,000

The first successful run occurred with latest completed market data through:

2026-07-02

The output was approximately:

SOXL close: $181.47
SOXL z-score: -1.531
QQQ close: $712.60
QQQ MA50: $708.51
QQQ above MA50: True
Oversold episode start: False
Buy signal: False

ACTION:
NO TRADE

The bot created/used:

data/paper_state.json
data/paper_daily_log.csv
data/paper_trade_log.csv

The existing bot is stateful.

The paper bot should now be carefully updated to the frozen fast strategy rather than creating multiple conflicting paper systems without clear naming.

# 13. IMMEDIATE NEXT STEPS

The next bot should prioritize the following work.

## STEP 1 — Preserve research state

Create a clean project checkpoint.

Do not delete old scripts or overwrite research outputs.

Suggested structure:

soxl-bot/

```
data/

research/
    old research scripts and outputs

strategy/
    signal.py
    regime.py
    exits.py
    sizing.py

paper/
    paper_bot.py
    portfolio.py

reports/
    performance.py
    equity_curve.py
```

The exact structure can vary, but separate:

research code

from

production-like paper-trading code.

## STEP 2 — Update paper bot to fast strategy

Change the paper strategy to:

SOXL 5-day z-score
threshold -1.50
episode-start logic
QQQ > 50-day MA
signal after close
entry next open
50% paper allocation
exit at close of holding day 4
no simple fixed stop

Be extremely careful about the day-count convention.

The implementation must match the research convention exactly.

## STEP 3 — Add duplicate-run protection

The paper bot currently logs every execution.

It should not:

* process the same completed market date twice,
* duplicate daily log rows,
* create duplicate pending entries,
* increment holding-day state because the script was run twice.

Use the latest processed market date in state or log data.

Repeated execution against identical market data should be idempotent.

## STEP 4 — Validate implementation parity

Before relying on the paper bot, verify that:

Given the same historical data,

the production signal function produces exactly the same signal dates as the research implementation.

This is important.

Do not assume that similar-looking code is equivalent.

Check:

* rolling standard deviation convention,
* adjusted data convention,
* threshold inequality,
* episode-start definition,
* QQQ date alignment,
* entry timing,
* holding-day counting,
* exit timing,
* slippage convention.

## STEP 5 — Improve paper logs

Daily log should include at minimum:

run timestamp
latest completed market date
SOXL close
5-day rolling mean
5-day rolling standard deviation
5-day z-score
QQQ close
QQQ MA50
QQQ above MA50
oversold
episode_start
buy_signal
current state
pending entry
entry date
entry price
days held
current marked P/L
paper cash
paper marked equity
next action
reason

## STEP 6 — True mark-to-market accounting

Track portfolio equity daily while a position is open.

Do not only update equity when a trade closes.

Need:

cash
shares
entry price
current SOXL close
position market value
total marked equity
running equity peak
current drawdown
maximum mark-to-market drawdown

## STEP 7 — Paper trade without changing rules

The strategy should be frozen for an initial forward observation period.

Suggested target:

approximately 2–3 months of paper operation

but judge evidence primarily by number and quality of genuinely unseen signals, not calendar duration alone.

Do not change the strategy because:

* one trade loses,
* SOXL moves sharply without triggering,
* a near-threshold signal rebounds,
* recent news creates FOMO.

Log these observations instead.

# 14. RESEARCH NEXT STEPS — LATER, NOT IMMEDIATELY

After meaningful forward evidence exists, possible research directions include:

## A. Failure-case analysis

Study losing trades.

Ask:

* Were they associated with QQQ barely above MA50?
* Were they associated with unusually large overnight gaps?
* Did semiconductor sector weakness differ from broad-tech weakness?
* Were they clustered around major macro events?
* Was volatility unusually high?

## B. Regime filter improvement

Only if justified by evidence.

Potential variables could include:

QQQ distance above MA50
QQQ MA50 slope
SOXX/SMH trend state
volatility regime
market breadth

Do not add many filters simultaneously.

## C. Exit research

Potential future exits:

mean-reversion completion exit
z-score normalization exit
rebound threshold exit
time exit
volatility-adjusted exit

Do not broadly optimize these now.

## D. ML filter

Only after enough event data exists.

Potential ML task:

Given that a deterministic oversold signal occurred, estimate the probability or expected magnitude of a successful rebound.

Potential features:

signal z-score
1-day return
3-day return
5-day return
realized volatility
QQQ distance from MA50
QQQ MA50 slope
SOXX or SMH trend
volume shock
overnight gap
market volatility state

Avoid using highly overlapping daily rows as if they were independent examples.

The natural unit is likely the signal event, not every trading day.

# 15. IMPORTANT METHODOLOGICAL RULES

The next bot should follow these rules.

## Rule 1: Do not repeatedly optimize the same history

The project has already done substantial exploration on 2021–2026 data.

Further optimization increases data-mining risk.

## Rule 2: Distinguish research results from portfolio results

Do not confuse:

average trade return

with:

account return.

Do not confuse:

compounded trade returns

with:

a realistic portfolio equity curve.

## Rule 3: Respect overlapping trades

Some early research tables allowed overlapping signal observations.

Later portfolio comparisons explicitly prevented overlapping positions.

Always state which methodology is being used.

## Rule 4: Respect daily-bar ambiguity

If a strategy has both a stop and target and both are touched in one daily candle, the ordering is unknown without intraday data.

Earlier work conservatively assumed stop first.

The current frozen fast candidate has no fixed stop or target, so this specific ambiguity is currently less relevant.

## Rule 5: Prevent lookahead bias

Signal uses information available after today's close.

Entry occurs next trading day's open.

Never enter at the same day's close based on that completed close unless the strategy is explicitly redesigned and execution assumptions are justified.

## Rule 6: Adjusted-price consistency

Research used yfinance with:

auto_adjust=True

Be consistent across research and paper signal calculation.

## Rule 7: Avoid false precision

Historical statistics are estimates from small samples.

Do not claim that:

85.7% OOS win rate

means future trades have an 85.7% probability of winning.

There were only approximately 14 walk-forward OOS trades.

# 16. CURRENT INTERPRETATION

The strongest current conclusion is not:

"5 days and -1.50 are magical numbers."

The stronger conclusion is:

There is evidence of a short-term SOXL mean-reversion effect in the modern sample when sharp short-term weakness occurs while the broader QQQ trend remains healthy.

The promising parameter neighborhood appears approximately around:

signal window:
5–6 days, with broader evidence around 4–8

holding period:
approximately 4–5 sessions

regime:
QQQ above 50-day MA

The exact frozen paper implementation is:

5D z < -1.50
first oversold episode day
QQQ > MA50
next-open entry
50% paper allocation
Day-4 close exit
no fixed stop

# 17. HOW TO WORK WITH THE USER

The user wants to learn, not only receive scripts.

When introducing a new test:

1. explain the question the test answers,
2. explain why the test is necessary,
3. give the code,
4. inspect the output,
5. explain the result in plain trading language,
6. distinguish what was learned from what remains unknown.

Teach concepts as they become relevant:

expectancy
win rate versus payoff ratio
drawdown
MAE
MFE
slippage
spread
overnight gap risk
leverage decay
volatility drag
lookahead bias
selection bias
multiple testing
walk-forward validation
overfitting
regime dependence
position sizing
mark-to-market accounting

Do not overwhelm the user with unrelated theory before it becomes relevant.

# 18. FINAL INSTRUCTION TO NEXT BOT

Do not restart parameter discovery.

The immediate task is:

1. inspect the existing project structure if provided,
2. preserve existing research files,
3. update the paper bot from the old 20D strategy to the frozen fast strategy,
4. make execution idempotent,
5. verify research/paper signal parity,
6. add proper daily mark-to-market tracking,
7. begin genuine forward observation.

The project has moved from:

"Can we find a backtest that looks good?"

to:

"Can a frozen, reproducible strategy behave sensibly on genuinely unseen data?"

That is the current phase.
