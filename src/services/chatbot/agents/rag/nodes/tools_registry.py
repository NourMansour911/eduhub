from typing import Any, Dict, List


def get_default_tools_registry() -> List[Dict[str, Any]]:

	return [
		{
			"name": "ask_in_specific_lecture_by_lecture_id",
			"description": "Search vector DB for chunks in a lecture.",
			"usage": "When to use: query content limited to a specific lecture",
			"args_schema": {
				"lecture_id": "str",
				"query": "str",
			},
		},
		{
			"name": "ask_in_the_whole_course_by_course_id",
			"description": "Search vector DB across a course.",
			"usage": "When to use: search all lectures in a course for relevant chunks.",
			"args_schema": {
				"course_id": "str",
				"query": "str",
			},
		},
		{
			"name": "search_in_sessions_history",
			"description": "Search the user's past sessions.",
			"usage": "When to use: only if the intent that.",
			"args_schema": {
				"student_id": "$student_id",
				"query": "str",
			},
		},
		{
			"name": "ask_in_legal_regulations",
			"description": "Search legal and regulatory lectures.",
			"usage": "When to use: ask regulatory or legal questions that must reference official materials.",
			"args_schema": {
				"query": "str",
			},
		},
		{
			"name": "get_course_id_by_course_name",
			"description": "Resolve a course id from its name.",
			"usage": "When to use: map a user-provided course name (approximately) to its internal id.",
			"output": {
				"course_id": "str",
				"course_name": "str"
			},
			"args_schema": {
				"student_id": "$student_id",
				"course_name": "str",
			},
		},
		{
			"name": "get_lecture_id_by_lecture_name",
			"description": "Resolve a lecture id from its title.",
			"usage": "When to use: map a lecture title (approximately) to its internal id within a course.",
			"output": {
				"lecture_id": "str",
				"lecture_name": "str"
			},
			"args_schema": {
				"course_id": "str",
				"lecture_name": "str",
			},
		},
		{
			"name": "get_course_details_by_course_id",
			"description": "Fetch course metadata by course id.",
			"usage": "When to use: retrieve course details (title, description, instructor) for display or validation.",
			"output": {
				"course_id": "str",
				"title": "str",
				"description": "str",
				"instructor": "str"
			},
			"args_schema": {
				"course_id": "str",
			},
		},
		{
			"name": "get_all_student_courses_ids_and_names",
			"description": "List a student's courses.",
			"usage": "When to use: enumerate available courses for a student.",
			"output": {
				"courses": "list[dict] (course_id, course_name)",
				"total": "int"
			},
			"args_schema": {
				"student_id": "str",
			},
		},
		{
			"name": "get_lecture_whole_content_by_lecture_id",
			"description": "Return the full lecture content by lecture id.",
			"usage": "When to use: obtain the complete lecture text for quoting, analysis, or chunking.",
			"output": {
				"content": "str",
				"lecture_id": "str"
			},
			"args_schema": {
				"lecture_id": "str",
			},
		},
		{
			"name": "get_lecture_summary_by_lecture_id",
			"description": "Return a lecture summary by lecture id.",
			"usage": "When to use: get a concise overview of a lecture when full content is not required.",
			"output": {
				"summary": "str",
				"lecture_id": "str",
				"level": "int (summary level if supported)"
			},
			"args_schema": {
				"lecture_id": "str",
			},
		},
	]