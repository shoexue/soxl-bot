# SOXL 30-minute regime review — 2026-07-29

## Decision

Keep `fast_30m_validated_v4` as the frozen paper lane. Do not promote a new live
rule from this sample.

Continue `adaptive_30m_research_v1` in shadow mode and add
`fast_30m_stress_guard_v5_research` to the robustness comparison. V5 uses the
existing v4 signal, waits for the next 30-minute bar's open, and permits at most
one entry per session. The guard is intended to reduce repeated falling-knife
attempts during a sector cascade.

## What changed in the market

The pulled daily paper history now runs through July 28. SOXL fell from $192.26
on July 10 to $109.54 on July 28, approximately 43%. Its latest completed daily
five-session return was -30.9%, and it was 58.9% below its rolling 20-session
high.

The news is consistent with a semiconductor-specific regime shock rather than
an ordinary QQQ dip:

- Axios described July as a disastrous month for semiconductors after parabolic
  gains, with memory and other AI-chip momentum reversing.
- AP reported broad weakness in AI-linked stocks on July 29, including a 3.6%
  Nvidia decline and a 10.8% KLA decline despite KLA beating profit and revenue
  expectations.
- The Guardian linked the global chip selloff to concern about debt-financed AI
  data-center expansion and reported double-digit July 28 declines in Samsung
  and SK Hynix.
- Reuters had already reported a greater-than-$1 trillion loss in U.S.-traded
  chipmaker value after Broadcom's outlook disappointed, followed by concern
  that the AI trade had become over-leveraged.

Sources: [Axios](https://www.axios.com/2026/07/29/chips-stocks-ai-china),
[Associated Press](https://apnews.com/article/b8bfaf782877957bbaa7196b70a4d725),
[The Guardian](https://www.theguardian.com/business/2026/jul/28/ai-sell-off-chip-stocks-sk-hynix-samsung),
[Reuters coverage](https://www.investing.com/news/economy-news/chipmakers-and-other-highflying-stocks-slide-as-ai-trade-wobbles-4798604).

SOXL itself targets 300% of its semiconductor index for one day, not three times
the index's cumulative multi-day return. Direxion explicitly lists compounding,
market-volatility, leverage, and semiconductor-concentration risks. That makes
execution delay, repeated entries, and mark-to-market drawdown especially
important in this regime. Source: [Direxion SOXL fund page](https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs).

## Refreshed 30-minute evidence

Yahoo supplied the maximum 60-day intraday window: 780 regular-session
30-minute bars from May 4 through July 29.

The legacy same-signal-close headline remains available for comparison:

| Lane | Trades | Return | Win rate | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| v4 | 30 | 12.9% | 56.7% | -6.1% |
| Adaptive v1 | 43 | 25.2% | 69.8% | -4.3% |

Those rows are optimistic because a rule cannot observe a completed close and
then retroactively fill at that close. The decision-grade check enters at the
next 30-minute open:

| Lane, 0.1% one-way slippage | Trades | Return | Win rate | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| v4 | 25 | 11.7% | 60.0% | -9.1% |
| V5 one-entry stress guard | 23 | 13.5% | 65.2% | -8.0% |
| Adaptive v1 | 34 | 29.2% | 70.6% | -6.5% |

For the latest 20 sessions, which begin July 1, the causal 0.1%-slippage returns
were +3.2% for v4, +4.5% for V5, and +7.1% for adaptive v1. At 0.3% one-way
slippage, full-window returns fell to +6.2%, +8.4%, and +20.6%, respectively.
At 0.5%, v4 retained only +1.1%.

Interpretation: the fast mean-reversion effect survived this selloff, but the
v4 edge is execution-cost sensitive and its intra-trade drawdown worsened under
causal fills. The one-entry guard improved v4's return, win rate, and drawdown
in this sample. Adaptive v1 remained strongest, but it is still a small,
single-vendor, 60-day research sample.

## Modern daily mean-reversion context

The daily context study uses 2021 onward and separates shock clusters by ten
sessions. After non-overlapping five-day SOXL falls of at least 30%:

| Forward window | Events | Median return | Positive rate | Worst result |
| --- | ---: | ---: | ---: | ---: |
| 1 session | 11 | +1.4% | 54.5% | -23.5% |
| 3 sessions | 11 | -3.3% | 36.4% | -27.7% |
| 5 sessions | 11 | +6.9% | 63.6% | -15.6% |

The distribution supports a five-session rebound tendency, not an immediate or
reliable bottom. Three-session outcomes were more often negative than positive,
and the left tail remained severe. This is consistent with waiting for
confirmation, limiting repeated intraday attempts, and keeping position size at
50% during research.

## Remaining gates

- Accumulate forward shadow evidence for both adaptive v1 and the V5 guard.
- Obtain a longer independent 30-minute history from a source other than
  Yahoo's 60-day window.
- Re-run next-open, cost-stress, and chronological checks on that independent
  history.
- Do not promote based on the current full-sample parameter winner or news
  narrative.

