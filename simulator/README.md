# Brand X budget mix simulator

A one-page companion to my Brand X case deck (Novartis Accelerated Leadership Program, IIM Bangalore campus
selection, Nov 2026). All data is the illustrative case data, not a real forecast.

## Use it
Open `index.html` in any browser. It runs offline, with no server and no external calls.

## What is on the page
- **Current mix** and **Recommended mix** buttons, and a **Download CSV** button for whatever mix is on screen.
- One card per market with sliders for field force, digital and patient support. Medical events take the remainder.
- Three results at the top: sales impact a year (up or down), money moved between channels, and a check on the 25% rule.

## How the impact is worked out
Each dollar earns the return in Exhibit 3: field force 1.8, digital 3.1, medical events 1.5, patient support 2.4.
Field force adds nothing above 55% of a market's budget and digital earns 1.5 above 30%. The impact is the
difference against the current mix. These are the same rules as `budget_optimizer.py`, so the recommended mix
shows USD 5.76m moved and USD 10.2m of modelled gain, as in the deck.
