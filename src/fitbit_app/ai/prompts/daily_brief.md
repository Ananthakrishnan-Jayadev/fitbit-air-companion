Write today's brief for {{ day }}.

DATA:
```json
{{ data }}
```

Return JSON with:
- `headline`: one sentence on how the user's body looks today.
- `summary`: 3-5 sentences. Mention recovery and what drove it, last night's sleep, and any
  notable deviation from normal. Use only the numbers above.
- `tips`: 1-3 practical tips for today. Match training advice to `strain_target` when present.
  Each tip has a short `title`, a one or two sentence `detail` that points to the data, and a
  `category` that is exactly one of: sleep, training, recovery, stress, activity, health.

Reply with the JSON object only: no markdown, no code fences, no other text.
