# Brand X budget reallocation

A small model behind my case presentation for the Novartis Accelerated Leadership Program
(IIM Bangalore campus selection, Nov 2026). The case data is illustrative and comes from the candidate pack.

## The question
Brand X sells USD 400m across five markets. Growth fell from 24% to 13%. How should the USD 60m
commercial budget be reallocated across markets and channels, with no increase in the total?

## What the script does
1. **Diagnosis.** Splits the 11 lost points of growth into the part shared by every market and the part
   specific to markets C and D, where a competitor launched.
2. **Optimiser.** A linear programme (`scipy.optimize.linprog`) finds the channel mix that adds the most
   sales in each market. It respects the case rules (total flat, no more than 25% of a market's budget
   moved, field force flat above 55%, digital falling above 30%) and my own guardrails, listed at the
   top of the file.
3. **Sensitivity.** 10,000 runs with each channel return varied by 30% either way and only 50 to 100% of
   the gain realised, to test whether the plan still beats today's mix.
4. **Bridge and deck checks.** Shows where the gain comes from channel by channel, and prints every other
   figure quoted in the deck so nothing rests on hand arithmetic.
5. **Charts.** Sales trend, growth by market, spend against growth, sales bridge, growth waterfall, mix
   before and after, and the sensitivity distribution.

## Run it
```
pip install -r requirements.txt
python budget_optimizer.py
```
On Windows use `py -3 budget_optimizer.py`. Results land in `output/`: `summary.txt`, `allocation.csv`
and seven PNG charts. The sensitivity test uses a fixed seed, so every run gives the same numbers.

## Results
| Market | Field force | Digital | Medical events | Patient support | Moved, USD m | Gain, USD m |
|---|---|---|---|---|---|---|
| A | 55% to 50% | 15% to 25% | 20% to 15% | 10% | 1.40 | 2.03 |
| B | 50% | 20% to 25% | 20% to 15% | 10% | 0.55 | 0.88 |
| C | 60% to 50% | 10% to 20% | 20% to 15% | 10% to 15% | 2.25 | 3.97 |
| D | 62% to 54% | 8% to 16% | 20% to 15% | 10% to 15% | 1.56 | 3.30 |
| E | 40% | 30% | 15% | 15% | 0 | 0 |

- USD 5.76m moves between channels, about 10% of the budget. No market moves more than 15%.
- The modelled gain is USD 10.2m a year if field spend above 55% adds nothing, and USD 7.3m if it still earns 1.8.
- In the sensitivity test, eight runs in ten fall between USD 4.6m and 11.1m, and every run beats today's mix.
- With the 25% rule alone and none of my guardrails, the model would move USD 15.0m for USD 21.5m.

These are model results built on indicative returns. They become a forecast only after a test in market.

## Assumptions that are mine
| Assumption | Value | Why |
|---|---|---|
| Country totals held flat | Yes | The data pack gives returns by channel, not by market |
| Field force floor | 50% of budget | The competitor has about twice as many reps in C and D |
| Medical events floor | 15% | Keeps medical credibility. Market E already runs at 15% |
| Patient support | Never cut, capped at 15% | Protects the existing patient base. No evidence beyond E's level |
| Channel growth | No more than double in a year | Content, medical-legal review and hiring take time |
| Return past a threshold | Field 0, digital 1.5 | "Flat" and "falls" in Exhibit 3, turned into numbers |

Change any of them at the top of `budget_optimizer.py` and run again.

## Files
| Path | What it is |
|---|---|
| `budget_optimizer.py` | Diagnosis, optimiser, sensitivity test and charts |
| `requirements.txt` | Python packages needed |
| `output/` | Results from my run: summary, allocation table and charts |
| `simulator/` | One-page browser simulator that uses the same rules as the script |
