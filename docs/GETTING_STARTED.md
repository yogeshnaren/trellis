# Getting started

This page takes you from a fresh checkout to asking Trellis a question in plain English in under
five minutes. No Python or SQL background is required.

**What it is:** a chat-like tool where you type a question about a music-store database (for
example "which country spends the most?") and it writes and runs the SQL for you, showing the
answer as a table.

## 1. One-time setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # installs `uv`, the Python tool runner
./scripts/setup_chinook.sh                         # downloads the sample database
uv sync                                             # installs project dependencies
cp .env.example .env                                # creates your local config file
```

### Bring your own key

Trellis calls [Fireworks AI](https://fireworks.ai) with **your** API key. Open `.env` in any
text editor and set:

```
FIREWORKS_API_KEY=your-key-here
FIREWORKS_MODEL=accounts/fireworks/models/deepseek-v4p1-flash   # the default; optional
```

- The key lives only in `.env`, which is gitignored. It is never committed, logged, or written
  to the spend ledger.
- `OPENROUTER_API_KEY` is optional. Only the benchmark path reads it, and only for one
  experimental decision model.
- `FIREWORKS_MODEL` picks the model. The default, `deepseek-v4p1-flash`, is the one every headline
  benchmark number in the README was measured on. To try another, set it here and check it first with
  `uv run python -m benchmark.preflight --models <model>`.
- Two spend caps protect you: a `$6` shared project ceiling (`FIREWORKS_BUDGET_USD`) and a `$2`
  per-session allowance (`SESSION_BUDGET_USD`).

## 2. Start the chat CLI

```bash
uv run trellis
```

You'll see a banner with the model, database, and remaining budget, then a `Question:>` prompt:

```
Question:> What are the top 5 best-selling genres by total sales?
Question:> Which employee has the most customers assigned to them?
Question:> Now show me the same thing but for the bottom 5 instead
```

Every answer is a table followed by a dim status line: time taken, tokens used, cost, and
remaining budget. Follow-ups ("now show me just the top 3", "what about only from Brazil?") work
because the tool remembers the SQL from your last question, but not its results.

| Type this | What it does |
|---|---|
| `/schema` | Shows the database tables and columns being used |
| `/last` | Re-prints the most recent SQL query generated |
| `/clear` | Forgets conversation history and starts fresh |
| `exit` or `quit` | Leaves the CLI |

Press `Ctrl+C` at any time to quit.

## 3. Everyday commands

| I want to... | Run this |
|---|---|
| Ask questions interactively | `uv run trellis` |
| Check the code still works after a change | `uv run pytest` |
| Check code style | `uv run ruff check src benchmark tests` |
| Check types | `uv run mypy src benchmark` |
| Verify a model works before benchmarking it | `uv run python -m benchmark.preflight --budget 0.05` |
| Compare models on Chinook | see the bake-off commands in the [README](../README.md#reproduce) |
| Benchmark against BIRD Mini-Dev | see the [README](../README.md#reproduce) |
| Regenerate the README's charts and CLI captures | `uv run python scripts/render_readme_assets.py` |
| See the latest Chinook report | open `benchmark/results/report.md` |
| See the latest BIRD report | open `benchmark/results/bird_report_minidev_gate1.md` |
| See sample question, SQL, answer triples | open `data/dev_answers.json` |

## 4. If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `FIREWORKS_API_KEY is not set` | Add the key to `.env` (step 1), or `export FIREWORKS_API_KEY=...` in your shell |
| `model-unavailable: Model ... is not available to this API key` | Your key cannot call the configured model. Set `FIREWORKS_MODEL` to one it can, and confirm with `benchmark.preflight` |
| "Shared project budget exhausted" | The project-wide spend ceiling was hit. Raise `FIREWORKS_BUDGET_USD` in `.env` if you are sure, or inspect the ledger `benchmark/results/.spend.sqlite` |
| "This CLI session's soft allowance is exhausted" | You spent the per-session cap. Restart the CLI for a fresh allowance |
| A query returns an error instead of a table | The tool rejected or failed to run the generated SQL. Rephrase the question. Nothing destructive can happen because the connection is read-only |
| `uv: command not found` | Re-run the install line in step 1, then open a new terminal |
