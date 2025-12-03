This file documents how stats are embedded and how to test locally.

- The template `templates/index.html` now embeds `stats` JSON in a hidden script tag with id `stats-data` and type `application/json`.
- Chart.js reads that element's textContent and `JSON.parse()`s it to create charts.

How to run locally:

```bash
python3 app.py
# open http://127.0.0.1:5000
```

If charts do not render, check:
- Server logs for template rendering errors.
- Browser console for JSON parse errors.
- That `stats` in server is a JSON-serializable dict (no sets or custom objects).
