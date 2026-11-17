# Contributing

Thanks for looking! This project keeps a few promises, and every change
should keep them too.

1. **Readable by a beginner.** Follow [design/code-standard.md](design/code-standard.md).
   `uv run python scripts/check_readability.py` must pass.
2. **Tested for real.** Write the failing test first. Use the real database
   and the stub server (`tests/stub_server.py`) instead of mocking the code
   you are testing.
3. **Every check green:**
   ```bash
   uv run pytest --cov --cov-fail-under=90
   uv run ruff check . && uv run ruff format --check .
   uv run python scripts/check_readability.py
   uv run bandit -c pyproject.toml -r . -q
   ```
4. **Honest docs.** Update the app's `README.md` and `docs/CODE-TOUR.md` when
   you add a file or a concept. Never claim something works with a real
   platform until it has been run with real credentials.
5. **Small commits** with a clear, imperative subject line.

Start with [docs/CODE-TOUR.md](docs/CODE-TOUR.md).
