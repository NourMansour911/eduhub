import csv
import requests

ENDPOINT = "http://localhost:5000/essay/grade-batch"
ANSWER_IID = "69fa8d41e515fab033df86bf"
INPUT_CSV = "underfitting_noisy_answers_v2_normalized_sorted.csv"

# Keep requests reasonably sized for the LLM-backed endpoint.
# Smaller chunks reduce the chance of hitting the HTTP timeout.
CHUNK_SIZE = 10
REQUEST_TIMEOUT = 300

results = []

with open(INPUT_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)


def _chunks(seq, n):
    if not n:
        yield seq
        return
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


global_index = 0
for batch_rows in _chunks(rows, CHUNK_SIZE):
    payload = {
        "items": [
            {
                "question_id": ANSWER_IID,
                "answer": (row.get("answer") or "").strip(),
            }
            for row in batch_rows
        ]
    }

    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json() or {}

        batch_results = data.get("results") or []
        if len(batch_results) != len(batch_rows):
            raise RuntimeError(
                f"Batch size mismatch: sent {len(batch_rows)} items, got {len(batch_results)} results"
            )

        for row, result in zip(batch_rows, batch_results):
            global_index += 1
            expected_score = float(row.get("expected_score") or 0.0)
            student_answer = (row.get("answer") or "").strip()
            system_score = float(result.get("score") or 0.0)

            diff = abs(system_score - expected_score)

            results.append(
                {
                    "index": global_index,
                    "question_id": result.get("question_id"),
                    "answer": student_answer,
                    "expected": expected_score,
                    "system": system_score,
                    "diff": diff,
                }
            )

            # Print student answer (trimmed), expected, system and difference
            short_ans = (student_answer[:120] + "...") if len(student_answer) > 120 else student_answer
            print(
                f"[{global_index:2d}] "
                f"Answer: {short_ans} | "
                f"Expected: {expected_score:.2f} | "
                f"System: {system_score:.4f} | "
                f"Diff: {diff:.3f}"
            )

    except Exception as e:
        global_index += len(batch_rows)
        print(f"[batch ending at {global_index}] ERROR: {str(e)}")

# stats
valid_results = [r for r in results if 'diff' in r]

if valid_results:
    avg_diff = sum(r['diff'] for r in valid_results) / len(valid_results)
    max_diff = max(r['diff'] for r in valid_results)
    min_diff = min(r['diff'] for r in valid_results)

    print(f"\n{'='*50}")
    print(f"Average difference: {avg_diff:.3f}")
    print(f"Min difference: {min_diff:.3f}")
    print(f"Max difference: {max_diff:.3f}")