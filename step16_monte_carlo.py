import pandas as pd
import numpy as np


# ============================================================
# 1. SETTINGS
# ============================================================

STARTING_CAPITAL = 10_000

N_SIMULATIONS = 20_000

RANDOM_SEED = 42


POSITION_SIZES = {
    "25% Allocation": 0.25,
    "50% Allocation": 0.50,
    "75% Allocation": 0.75,
    "100% Allocation": 1.00,
}


np.random.seed(
    RANDOM_SEED
)


# ============================================================
# 2. LOAD STEP 15 TRADES
# ============================================================

trades = pd.read_csv(
    "data/position_sizing_trades.csv",
    parse_dates=[
        "signal_date",
        "entry_date",
        "exit_date",
    ],
)


# Use one sizing strategy only to extract the underlying
# SOXL position returns.
#
# The position_return is identical across sizing methods.

base_trades = trades[
    trades["strategy"]
    == "100% Allocation"
].copy()


base_trades = (
    base_trades
    .sort_values("signal_date")
    .reset_index(drop=True)
)


trade_returns = (
    base_trades["position_return"]
    .to_numpy()
)


N_TRADES = len(
    trade_returns
)


print()
print("=" * 110)
print("STEP 16 — MONTE CARLO STRESS TEST")
print("=" * 110)

print()

print(
    f"Historical trades loaded: "
    f"{N_TRADES}"
)

print(
    f"Simulations per method: "
    f"{N_SIMULATIONS:,}"
)

print()

print(
    "Historical position returns:"
)

for i, value in enumerate(
    trade_returns,
    start=1,
):

    print(
        f"Trade {i:2d}: "
        f"{value:+.2%}"
    )


# ============================================================
# 3. SIMULATE ONE ACCOUNT PATH
# ============================================================

def simulate_path(
    returns,
    position_fraction,
):

    capital = STARTING_CAPITAL

    equity = [
        capital
    ]


    for position_return in returns:

        account_return = (

            position_fraction

            * position_return
        )


        capital = (

            capital

            * (
                1 + account_return
            )
        )


        equity.append(
            capital
        )


    equity = np.array(
        equity
    )


    running_peak = np.maximum.accumulate(
        equity
    )


    drawdowns = (

        equity

        / running_peak

    ) - 1


    max_drawdown = (
        drawdowns.min()
    )


    total_return = (

        capital

        / STARTING_CAPITAL

    ) - 1


    return {
        "final_capital":
            capital,

        "total_return":
            total_return,

        "max_drawdown":
            max_drawdown,
    }


# ============================================================
# 4. RUN SHUFFLE TEST
#
# Same exact 12 returns every simulation.
# Only their order changes.
#
# This isolates sequence risk.
# ============================================================

shuffle_rows = []


for strategy_name, position_fraction in (
    POSITION_SIZES.items()
):

    print()

    print(
        f"Running shuffle test: "
        f"{strategy_name}"
    )


    for simulation in range(
        N_SIMULATIONS
    ):

        simulated_returns = (
            np.random.permutation(
                trade_returns
            )
        )


        result = simulate_path(

            returns=
                simulated_returns,

            position_fraction=
                position_fraction,
        )


        shuffle_rows.append({

            "simulation":
                simulation + 1,

            "strategy":
                strategy_name,

            "position_fraction":
                position_fraction,

            "final_capital":
                result[
                    "final_capital"
                ],

            "total_return":
                result[
                    "total_return"
                ],

            "max_drawdown":
                result[
                    "max_drawdown"
                ],
        })


shuffle_results = pd.DataFrame(
    shuffle_rows
)


# ============================================================
# 5. RUN BOOTSTRAP TEST
#
# Draw 12 trades WITH replacement.
#
# This means:
# - some historical trades may appear multiple times
# - some may not appear at all
# - win/loss frequency can vary
#
# This is more stressful than simple shuffling.
# ============================================================

bootstrap_rows = []


for strategy_name, position_fraction in (
    POSITION_SIZES.items()
):

    print()

    print(
        f"Running bootstrap test: "
        f"{strategy_name}"
    )


    for simulation in range(
        N_SIMULATIONS
    ):

        simulated_returns = (
            np.random.choice(

                trade_returns,

                size=N_TRADES,

                replace=True,
            )
        )


        result = simulate_path(

            returns=
                simulated_returns,

            position_fraction=
                position_fraction,
        )


        bootstrap_rows.append({

            "simulation":
                simulation + 1,

            "strategy":
                strategy_name,

            "position_fraction":
                position_fraction,

            "final_capital":
                result[
                    "final_capital"
                ],

            "total_return":
                result[
                    "total_return"
                ],

            "max_drawdown":
                result[
                    "max_drawdown"
                ],
        })


bootstrap_results = pd.DataFrame(
    bootstrap_rows
)


# ============================================================
# 6. SUMMARY FUNCTION
# ============================================================

def summarize_simulations(
    results,
    method_name,
):

    rows = []


    for strategy_name, group in (
        results.groupby("strategy")
    ):

        rows.append({

            "method":
                method_name,

            "strategy":
                strategy_name,

            "position_fraction":
                group[
                    "position_fraction"
                ].iloc[0],


            # -----------------------------------------------
            # FINAL CAPITAL
            # -----------------------------------------------

            "median_final_capital":
                group[
                    "final_capital"
                ].median(),

            "p05_final_capital":
                group[
                    "final_capital"
                ].quantile(0.05),

            "p95_final_capital":
                group[
                    "final_capital"
                ].quantile(0.95),


            # -----------------------------------------------
            # RETURNS
            # -----------------------------------------------

            "median_total_return":
                group[
                    "total_return"
                ].median(),

            "p05_total_return":
                group[
                    "total_return"
                ].quantile(0.05),

            "p95_total_return":
                group[
                    "total_return"
                ].quantile(0.95),


            # -----------------------------------------------
            # DRAWDOWN
            # -----------------------------------------------

            "median_max_drawdown":
                group[
                    "max_drawdown"
                ].median(),

            "p05_max_drawdown":
                group[
                    "max_drawdown"
                ].quantile(0.05),

            "worst_max_drawdown":
                group[
                    "max_drawdown"
                ].min(),


            # -----------------------------------------------
            # FAILURE PROBABILITIES
            # -----------------------------------------------

            "probability_of_loss":
                (
                    group[
                        "total_return"
                    ] < 0
                ).mean(),

            "probability_dd_over_10pct":
                (
                    group[
                        "max_drawdown"
                    ] <= -0.10
                ).mean(),

            "probability_dd_over_20pct":
                (
                    group[
                        "max_drawdown"
                    ] <= -0.20
                ).mean(),

            "probability_dd_over_30pct":
                (
                    group[
                        "max_drawdown"
                    ] <= -0.30
                ).mean(),

            "probability_dd_over_40pct":
                (
                    group[
                        "max_drawdown"
                    ] <= -0.40
                ).mean(),
        })


    return pd.DataFrame(
        rows
    )


# ============================================================
# 7. BUILD SUMMARIES
# ============================================================

shuffle_summary = summarize_simulations(

    results=
        shuffle_results,

    method_name=
        "Shuffle",
)


bootstrap_summary = summarize_simulations(

    results=
        bootstrap_results,

    method_name=
        "Bootstrap",
)


combined_summary = pd.concat(

    [
        shuffle_summary,
        bootstrap_summary,
    ],

    ignore_index=True,
)


# ============================================================
# 8. HISTORICAL PATH COMPARISON
# ============================================================

historical_rows = []


for strategy_name, position_fraction in (
    POSITION_SIZES.items()
):

    result = simulate_path(

        returns=
            trade_returns,

        position_fraction=
            position_fraction,
    )


    historical_rows.append({

        "strategy":
            strategy_name,

        "position_fraction":
            position_fraction,

        "historical_final_capital":
            result[
                "final_capital"
            ],

        "historical_total_return":
            result[
                "total_return"
            ],

        "historical_max_drawdown":
            result[
                "max_drawdown"
            ],
    })


historical_summary = pd.DataFrame(
    historical_rows
)


# ============================================================
# 9. SAVE OUTPUT FILES
# ============================================================

combined_summary.to_csv(
    "data/monte_carlo_summary.csv",
    index=False,
)


historical_summary.to_csv(
    "data/monte_carlo_historical.csv",
    index=False,
)


shuffle_results.to_csv(
    "data/monte_carlo_shuffle_results.csv",
    index=False,
)


bootstrap_results.to_csv(
    "data/monte_carlo_bootstrap_results.csv",
    index=False,
)


# ============================================================
# 10. PRINT MAIN SUMMARY
# ============================================================

print()
print("=" * 140)
print("MONTE CARLO SUMMARY")
print("=" * 140)
print()


print(
    combined_summary.to_string(

        index=False,

        formatters={

            "position_fraction":
                "{:.0%}".format,

            "median_final_capital":
                "${:,.2f}".format,

            "p05_final_capital":
                "${:,.2f}".format,

            "p95_final_capital":
                "${:,.2f}".format,

            "median_total_return":
                "{:.2%}".format,

            "p05_total_return":
                "{:.2%}".format,

            "p95_total_return":
                "{:.2%}".format,

            "median_max_drawdown":
                "{:.2%}".format,

            "p05_max_drawdown":
                "{:.2%}".format,

            "worst_max_drawdown":
                "{:.2%}".format,

            "probability_of_loss":
                "{:.2%}".format,

            "probability_dd_over_10pct":
                "{:.2%}".format,

            "probability_dd_over_20pct":
                "{:.2%}".format,

            "probability_dd_over_30pct":
                "{:.2%}".format,

            "probability_dd_over_40pct":
                "{:.2%}".format,
        }
    )
)


# ============================================================
# 11. PRINT HISTORICAL COMPARISON
# ============================================================

print()
print("=" * 110)
print("HISTORICAL PATH")
print("=" * 110)
print()


print(
    historical_summary.to_string(

        index=False,

        formatters={

            "position_fraction":
                "{:.0%}".format,

            "historical_final_capital":
                "${:,.2f}".format,

            "historical_total_return":
                "{:.2%}".format,

            "historical_max_drawdown":
                "{:.2%}".format,
        }
    )
)


# ============================================================
# 12. FINAL MESSAGE
# ============================================================

print()
print("Files saved:")

print(
    "data/monte_carlo_summary.csv"
)

print(
    "data/monte_carlo_historical.csv"
)

print(
    "data/monte_carlo_shuffle_results.csv"
)

print(
    "data/monte_carlo_bootstrap_results.csv"
)