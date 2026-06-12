"""Extract key metrics from eval result JSON files into a CSV."""

import csv
import json
from pathlib import Path

FIELDS = [
    "filename",
    "date",
    "time",
    "branch",
    "commit_hash",
    "judge_model",
    "test_case_id",
    "difficulty",
    "latency_s",
    "tool_call_count",
    "input_tokens",
    "output_tokens",
    "quality_score",
    "accuracy_judge_score",
]


def parse_filename(stem: str) -> dict:
    parts = stem.split("_")
    return {
        "date": parts[0],
        "time": parts[1],
        "branch": "_".join(parts[2:-2]),
        "commit_hash": parts[-2],
        "judge_model": parts[-1],
    }

def main():
    eval_dir = Path(__file__).parent.parent / "bot" / "eval_results"
    out_path = eval_dir / "summary.csv"
    json_files = sorted(eval_dir.glob("*.json"))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for path in json_files:
            with open(path, encoding="utf-8") as jf:
                cases = json.load(jf)
            file_parts = parse_filename(path.stem)
            for case in cases:
                writer.writerow({
                    "filename": path.name,
                    **file_parts,
                    "test_case_id": case.get("test_case_id"),
                    "difficulty": case.get("difficulty"),
                    "latency_s": case.get("latency_s"),
                    "tool_call_count": case.get("tool_call_count"),
                    "input_tokens": case.get("input_tokens"),
                    "output_tokens": case.get("output_tokens"),
                    "quality_score": case.get("quality_score"),
                    "accuracy_judge_score": case.get("accuracy_judge_score"),
                })

    print(f"Written {len(json_files)} files to {out_path}")

if __name__ == "__main__":
    main()
