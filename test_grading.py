import csv
import requests

ENDPOINT = "http://localhost:5000/essay/grade"
ANSWER_IID = "9664568b-fef3-4ae6-8ae3-eb872df4ebdf"
INPUT_CSV = "underfitting_noisy_answers_v2_normalized_sorted.csv"

results = []

with open(INPUT_CSV, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)

    for idx, row in enumerate(reader, 1):
        answer = row['answer'].strip()
        expected_score = float(row['expected_score'])

        payload = {
            "question_id": ANSWER_IID,
            "answer": answer
        }

        try:
            response = requests.post(
                ENDPOINT,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # safe parsing
            system_score = float(data.get('final_score') or 0.0)

            diff = abs(system_score - expected_score)

            results.append({
                'index': idx,
                'expected': expected_score,
                'system': system_score,
                'diff': diff,
            })

            print(
                f"[{idx:2d}] "
                f"Expected: {expected_score:.2f} | "
                f"System: {system_score:.4f} | "
                f"Diff: {diff:.3f}"
            )

        except Exception as e:
            print(f"[{idx}] ERROR: {str(e)}")

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