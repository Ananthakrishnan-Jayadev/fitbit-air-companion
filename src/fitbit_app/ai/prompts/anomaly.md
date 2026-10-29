The app flagged unusual signals for {{ day }}: {{ flags }}.

DATA:
```json
{{ data }}
```

Explain in plain language what these signals together could indicate (for example, the body
fighting an infection, accumulated fatigue, poor sleep, alcohol, or travel), without diagnosing.

Return JSON with:
- `headline`: one calm sentence.
- `explanation`: 2-4 sentences connecting the specific deviations above.
- `suggestions`: 1-3 practical things to do today.
- `see_doctor_if`: when it would be sensible to talk to a doctor.
