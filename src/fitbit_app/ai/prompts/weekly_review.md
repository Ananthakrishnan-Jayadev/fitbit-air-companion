Write a weekly review for the 7 days ending {{ day }}.

DATA (`this_week` and `previous_week` are daily averages; `days` lists each day):
```json
{{ data }}
```

Return JSON with:
- `headline`: one sentence summing up the week.
- `summary`: 3-6 sentences comparing this week with the previous one (recovery, sleep,
  strain, resting heart rate, HRV, activity). Use only the numbers above.
- `wins`: up to 3 things that went well.
- `watch`: up to 3 things to keep an eye on.
- `focus`: one concrete focus for next week.
