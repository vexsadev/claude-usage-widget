---
name: update-prices
description: Update the Claude API price table (PRICES in usage.py) when Anthropic adds a model or changes prices, and keep tests and README in sync.
---

# Update model prices

1. Get the current list prices (input, output, cache read per million tokens) from Anthropic's pricing
   page — never from memory. Note any special tiers (long-context surcharges, fast mode).
2. Edit `PRICES` in `src/claude_usage_widget/usage.py`:
   - key = model id prefix (`claude-<family>-<major>-<minor>`); longest prefix wins, so add specific ids
     before relying on a shorter fallback key.
   - value = `(input, output, cache_read)` in USD per MTok. Cache writes are derived (1.25x / 2x input).
   - Long-context or other special pricing goes in `request_cost` like `HAIKU55_LONG`.
3. If a new family name appears, check `usage.model_name` formats it (e.g. `claude-opus-5-5` -> `Opus 5.5`).
4. Add or adjust a test in `tests/test_usage.py` (`CostTests`) for each new or changed model.
5. Run `python -m unittest discover -s tests -v`.
6. If `demo.py` sample model names are now outdated, update them and regenerate media with the
   `regen-media` skill.
