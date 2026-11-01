"""
Answer-quality evaluation for the Voice-RAG backend.

Sends every question in eval/questions.json to the running backend and checks:
  - answer:  at least one of `expect_any` appears in the answer (case-insensitive)
  - source:  if `expect_source` is set, a retrieved chunk's title contains it

Usage (with Backend 1 running on :8000 and Backend 2 on :8001 for tools mode):
    python eval/run_eval.py                  # all questions
    python eval/run_eval.py --seed           # first add the sample document
    python eval/run_eval.py --mode pure      # only one mode
    python eval/run_eval.py --out results.json
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests

QUESTIONS_FILE = Path(__file__).parent / "questions.json"


def ask(base_url: str, q: dict) -> dict:
    """Runs one question; returns the result row."""
    started = time.time()
    try:
        res = requests.post(
            f"{base_url}/api/rag",
            json={"query": q["question"], "language": q.get("language", "en"), "sessionId": "eval"},
            headers={"x-backend-mode": q["mode"]},
            timeout=120,
        )
        data = res.json()
        if res.status_code != 200:
            raise RuntimeError(data.get("detail") or data)
        answer = data.get("answer", "")
        titles = [c.get("documentTitle", "") for c in data.get("retrievedChunks", [])]
        error = ""
    except Exception as e:
        answer, titles, error = "", [], str(e)

    answer_ok = any(word.lower() in answer.lower() for word in q["expect_any"])
    source = q.get("expect_source")
    source_ok = True if not source else any(source.lower() in t.lower() for t in titles)

    return {
        "id": q["id"],
        "mode": q["mode"],
        "passed": answer_ok and source_ok and not error,
        "answer_ok": answer_ok,
        "source_ok": source_ok,
        "seconds": round(time.time() - started, 1),
        "error": error,
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.getenv("PYTHON_BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--mode", choices=["pure", "standard", "tools"])
    parser.add_argument("--seed", action="store_true", help="ingest the sample SLT document first")
    parser.add_argument("--out", help="write full results (including answers) to this JSON file")
    args = parser.parse_args()

    if args.seed:
        key = os.getenv("ADMIN_API_KEY")
        res = requests.post(
            f"{args.url}/api/documents/seed",
            headers={"x-admin-key": key} if key else {},
            timeout=120,
        )
        print(f"Seed sample document: HTTP {res.status_code}")

    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if args.mode:
        questions = [q for q in questions if q["mode"] == args.mode]

    results = []
    print(f"{'id':<22} {'mode':<9} {'result':<6} {'answer':<7} {'source':<7} {'secs':>5}")
    for q in questions:
        r = ask(args.url, q)
        results.append(r)
        status = "PASS" if r["passed"] else ("ERROR" if r["error"] else "FAIL")
        print(f"{r['id']:<22} {r['mode']:<9} {status:<6} {str(r['answer_ok']):<7} {str(r['source_ok']):<7} {r['seconds']:>5}")
        if r["error"]:
            print(f"    error: {r['error'][:150]}")

    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} passed ({100 * passed // max(len(results), 1)}%)")
    for mode in ("pure", "standard", "tools"):
        rows = [r for r in results if r["mode"] == mode]
        if rows:
            print(f"  {mode:<9} {sum(r['passed'] for r in rows)}/{len(rows)}")

    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved results to {args.out}")


if __name__ == "__main__":
    main()
