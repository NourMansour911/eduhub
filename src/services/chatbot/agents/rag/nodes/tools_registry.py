from typing import Any, Dict, List


def get_default_tools_registry():
    return [
        {
            "name": "ask_in_specific_lecture_by_lecture_id",
            "desc": "Answers a question using vector search within a specific lecture.",
            "args": {"lecture_id": "str", "query": "str"},
            "returns": {"answer": "str"}
        },
        {
            "name": "ask_in_the_whole_course_by_course_id",
            "desc": "Answers a question using vector search across an entire course.",
            "args": {"course_id": "str", "query": "str"},
            "returns": {"answer": "str"}
        },
        {
            "name": "search_in_sessions_history",
            "desc": "Searches the student's past session history for answers.",
            "args": {"student_id": "$student_id", "query": "str"},
            "returns": {"answer": "str"}
        },
        {
            "name": "ask_in_legal_regulations",
            "desc": "Answers questions about legal and regulatory information.",
            "args": {"query": "str"},
            "returns": {"answer": "str"}
        },
        {
            "name": "get_lecture_id_by_lecture_name",
            "desc": "Finds the exact lecture_id for a given lecture name within a course.",
            "args": {"course_id": "str", "lecture_name": "str"},
            "returns": {"lecture_id": "str", "lecture_name": "str"}
        },
        {
            "name": "get_course_details_by_course_id",
            "desc": "Gets metadata and details for a course (e.g., doctor_name, hours, price).",
            "args": {"course_id": "str"},
            "returns": {"course_id": "str", "doctor_name": "str", "hours": "int", "price": "int"}
        },
        {
            "name": "get_lecture_whole_content_by_lecture_id",
            "desc": "Retrieves the complete, raw content of a lecture.",
            "args": {"lecture_id": "str"},
            "returns": {"lecture_content": "str"}
        },
        {
            "name": "get_lecture_summary_by_lecture_id",
            "desc": "Retrieves a summarized version of a lecture.",
            "args": {"lecture_id": "str"},
            "returns": {"summary": "str"}
        },
        {
            "name": "get_all_course_lectures_by_course_id",
            "desc": "Gets a list of all lectures in a course, ordered from oldest to newest.",
            "args": {"course_id": "str"},
            "returns": {"lectures": [{"id": "str", "title": "str"}]}
        },
    ]