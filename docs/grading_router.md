# Essay Grading API

Base path: `/essay`

## POST /essay/reference

Set the reference answer for later grading.

Request body

- `answer`: `string`

Response

- `question_id`: `string`

Example request

{
  "answer": "Explain the steps of cellular respiration."
}

Example response

{
  "question_id": "2f4df1c3-9f2d-4c8a-8e3c-3c2f8c3c8c11"
}

## POST /essay/grade

Grade a student answer against the stored reference answer.

Request body

- `question_id`: `string`
- `answer`: `string`

Response

- `score`: `float`

Example request

{
  "question_id": "2f4df1c3-9f2d-4c8a-8e3c-3c2f8c3c8c11",
  "answer": "Cellular respiration has glycolysis, Krebs cycle, and oxidative phosphorylation..."
}

Example response

{
  "score": 71.0
}

## Notes

- Store the returned `question_id` from `/essay/reference` and reuse it in `/essay/grade`.
