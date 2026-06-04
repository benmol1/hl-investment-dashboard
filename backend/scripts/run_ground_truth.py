"""Quick manual review of eval ground-truth SQL. Runs each query and prints results."""
import sys
from pathlib import Path


def _load_dotenv():
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        __import__("os").environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
__import__("os").environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-mode")
__import__("os").environ.setdefault("TELEGRAM_CHAT_ID", "0")

from backend.bot.eval import TEST_CASES, run_ground_truth

ids = set(sys.argv[1:]) or {tc.id for tc in TEST_CASES}

for tc in TEST_CASES:
    if tc.id not in ids:
        continue
    print(f"\n{'=' * 60}")
    print(f"[{tc.id}] {tc.difficulty} — {tc.question}")
    print(f"{'=' * 60}")
    try:
        rows = run_ground_truth(tc.ground_truth_sql)
        if not rows:
            print("  (no rows)")
        for row in rows:
            print(" ", row)
    except Exception as e:
        print(f"  ERROR: {e}")
