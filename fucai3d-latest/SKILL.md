---
name: fucai3d-latest
description: Use when querying the most recent China Welfare Lottery 3D draw results. Suitable when the user wants to check the latest Welfare Lottery 3D draw, the most recent issue's numbers, the first Baidu search result for "3d/Welfare Lottery 3D", or quickly return the issue number, date, and numbers. Also suitable for recording historical results after the query and, based on the history, providing entertainment-only suggested numbers for the next draw, hot and cold number analysis, and multi-strategy number recommendations.
---

# Latest China Welfare Lottery 3D Draw Results

When the user wants to query the most recent China Welfare Lottery 3D draw results:

1. Prefer using the browser tool to visit `https://www.baidu.com`
2. Search for `Fucai 3D`
3. Prefer reading the "Official Welfare Lottery 3D - Draw Results" card at the top of the Baidu results page
4. First extract the information currently shown by default:
   - Issue number
   - Draw date
   - Winning numbers
5. If the user asks to "update results", "fill in missed draws", "check the recent draws", or suspects that the numbers are wrong:
   - Do not rely only on the result shown by default in the current card
   - First check the issue/date selector above the winning numbers, such as a switchable entry like `Issue 2026086, 2026-04-06...`
   - Switch through the most recent issues one by one to verify them, checking at least the current issue and the previous 1 to 3 issues
   - If "historical draw results" text appears directly below the Baidu card or in the body of the search results, such as `Issue 2026086: 382 / Issue 2026085: 118 / Issue 2026084: 456`, use that issue-by-issue list as the basis for backfilling and correcting data
6. Only fall back to the China Welfare Lottery website or other authoritative sources when issue-by-issue verification cannot be completed from the Baidu results page, and clearly state the data source

After obtaining the result, perform these additional entertainment functions:

1. Use `/var/minis/shared/fucai3d/recommender.py update ISSUE DATE DIGITS` to write this draw result to the history file `/var/minis/shared/fucai3d/history.json`
2. If any issue numbers are missing, backfill the missing issues as well; if any incorrect numbers already exist in the history, correct the local history using the latest verified results
3. Use `/var/minis/shared/fucai3d/recommender.py bundle 5` to generate:
   - 5 sets of basic entertainment recommendations
   - 3 sets of cold-number preference recommendations
   - 3 sets of hot-number mixed recommendations
   - Frequencies of 0 to 9 in the recent window
   - Hot-number and cold-number summary
4. Clearly state that these suggested numbers are only "toy recommendations" generated from historical exclusion rules and simple frequency preferences, and do not represent any real predictive ability

Keep the output as concise as possible. Default format:

- Issue number: Issue XXXXXXX
- Draw date: YYYY-MM-DD
- Winning numbers: X X X
- History: updated / already exists / corrected
- If backfilled: backfilled Issue XXXXXXX, Issue XXXXXXX...
- Entertainment recommendations: A B C / D E F / ...
- Cold-number preference: A B C / D E F / ...
- Hot-number mix: A B C / D E F / ...
- Hot numbers in the last 30 issues: x, x, x...
- Cold numbers in the last 30 issues: x, x, x...
- Note: Based only on historical records for simple exclusion and frequency statistics; does not constitute predictive advice

Recommendation logic notes (no need to explain too much to the user):

- Prefer avoiding exact three-digit combinations that have appeared recently
- Avoid recent identical sum values as much as possible
- Avoid recent repeated patterns in adjacent digit pairs as much as possible
- Use the recent window to calculate hot and cold number frequencies
- If the history is too sparse or the constraints are too strict, fall back to random completion

If the Baidu results page cannot directly provide the winning numbers:

1. Try clicking the first result to continue reading
2. Prefer finding and parsing historical draw list text in the Baidu result body
3. If that still fails, check the China Welfare Lottery website or other authoritative sources
4. Clearly state the data source

If the retrieved information may not be from the latest issue, clearly state "based on current search results."
