---
name: error-handling
description: "Enforces service-layer exception architecture for Python FastAPI projects with custom exception classes, consistent status_code/error_code, centralized logging, and no duplicated schema validation."
---

# Error Handling Skill

## Purpose
This skill standardizes exception handling in the service layer.
It ensures all API-facing errors are custom classes with consistent structure.

## When To Use
Use this skill when:
- Creating a new service module.
- Refactoring existing service logic.
- Reviewing PRs for exception consistency.
- Replacing generic exceptions with custom domain exceptions.
- Defining error responses that must be predictable for clients.

## Core Rules

### 1) Ownership
- Exception shaping and raising MUST happen in service layer.
- Routers/controllers MUST NOT translate business exceptions.
- Routers/controllers SHOULD only call services and return data.

### 2) Inheritance
- All custom exceptions MUST inherit from AppException directly or indirectly.
- Service-level base exceptions SHOULD inherit from ServiceException.
- AppException remains the root error contract for API responses.

### 3) Shared vs Local Exception Files
- Shared exceptions used by multiple services MUST live in:
  src/services/service_exceptions.py
- Each small service MUST have local custom exceptions file for domain-specific errors.
- If an exception is reused by 2 or more service modules, move it to shared service_exceptions.py.

### 4) status_code and error_code
- Every custom exception class MUST define logical status_code.
- Every custom exception class MUST define explicit stable error_code.
- error_code MUST be uppercase and underscore-separated.
- Avoid ambiguous error_code values.

### 5) Logging
- Every service error path MUST be logged with get_logger.
- Prefer centralized logging in ServiceException constructor.
- Custom exceptions MUST NOT be logged before being raised if they already inherit logging behavior from ServiceException.
- Avoid duplicate logging for the same failure path.
- If pre-exception logging is absolutely necessary, the exception flow MUST ensure the same error is not logged again by the exception constructor.
- Log message MUST include contextual details when available.

### 6) Validation Boundaries
- Do NOT duplicate validation already handled by Pydantic schemas.
- When a parameter is explicitly typed (e.g. `lecture_id: str` not `Optional[str]`) in the schema, Pydantic enforces it.
- Do NOT re-validate emptiness, type correctness, or required fields in service layer.
- Service methods SHOULD only validate business rules:
  - Data existence in database (e.g. "Does this lecture exist in Mongo?")
  - Business logic constraints (e.g. "Is summary level between 0-2?")
  - External dependency results (e.g. "Did the LLM call succeed?")
- Skip service-level empty/type checks for fields already constrained in schema.
- Example to AVOID:
  ```python
  # BAD: lecture_id: str is already required in Pydantic schema
  if not lecture_id:
      raise SummarizeValidationError(...)
  ```
- Example to DO:
  ```python
  # GOOD: Check business rule, not basic presence
  lecture = await repo.get_lecture_by_lecture_id(lecture_id)
  if not lecture:  # Data existence is a business rule
      raise SummarizeNotFoundError(...)
  ```

### 7) Forbidden Patterns
- MUST NOT raise raw ValueError, RuntimeError, or generic Exception as API-facing errors.
- MUST NOT use ad-hoc error response formatting outside central exception handler.
- MUST NOT bypass custom exception classes in service logic.

## File Layout

- src/core/app_exceptions.py
- src/services/service_exceptions.py
- src/services/<service_name>/<service_name>_exceptions.py
- src/core/handler.py

## Naming Conventions

- Base service exception:
  <Domain>ServiceException
- Validation (business rules only, NOT schema-level):
  <Domain>ValidationError
  *Use ONLY for business rule violations (e.g., invalid level range, business constraint failures).*
  *Do NOT use for empty/type checks—Pydantic handles those.*
- Not found:
  <Domain>NotFoundError
- Conflict:
  <Domain>ConflictError
- External dependency failure:
  <Domain>ExternalError or <Domain>ProviderError

Error code format:
- DOMAIN_REASON
- Examples:
  LECTURE_NOT_FOUND
  EMBEDDING_GENERATION_FAILED
  REFERENCE_ANSWER_NOT_FOUND

## Templates

### Shared Base Exception Template
```python
from core.app_exceptions import AppException
from helpers import get_logger

logger = get_logger(__name__)

class ServiceException(AppException):
    def __init__(self, message="Service error", details=None, status_code=500, error_code="SERVICE_ERROR"):
        logger.error(
            message,
            extra={
                "status_code": status_code,
                "error_code": error_code,
                "details": details,
            },
        )
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )
```

### Local Service Exception Template
```python
from services.service_exceptions import ServiceException

class LectureServiceException(ServiceException):
    def __init__(self, message="Lecture service error", details=None, status_code=500, error_code="LECTURE_SERVICE_ERROR"):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )

class LectureValidationError(LectureServiceException):
    def __init__(self, message="Lecture validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="LECTURE_VALIDATION_ERROR",
        )

class LectureNotFoundError(LectureServiceException):
    def __init__(self, message="Lecture not found", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=404,
            error_code="LECTURE_NOT_FOUND",
        )
```

### Service Raise Pattern Template
```python
from services.summarize.summarize_exceptions import (
    SummarizeNotFoundError,
    SummarizeProcessingError,
)

async def summarize(self, lecture_id: str, level: int) -> str:
    # lecture_id and level are already validated by Pydantic schema
    # DO NOT check: if not lecture_id, if level < 0, etc.
    
    # DO validate: Business rules and data layer results
    lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
    if lecture is None:  # Data existence is a business rule
        raise SummarizeNotFoundError(details={"lecture_id": lecture_id})
    
    try:
        summary = await self._generate_summary(lecture.content, level)
        return summary
    except Exception as e:
        # External dependency failure (LLM chain)
        raise SummarizeProcessingError(
            message="Failed to generate summary",
            details={"error": str(e)}
        )
```

## Migration Checklist
- Identify all raised exceptions in service modules.
- Replace generic exceptions with domain custom classes.
- Ensure every custom class inherits from AppException lineage.
- Add status_code and error_code to all custom classes.
- Move cross-service exceptions to shared service_exceptions.py.
- Keep domain-specific exceptions in local service folders.
- Remove duplicated validation already covered by Pydantic.
- Ensure service error paths include logging.
- Verify central exception handler returns consistent response shape.

## PR Review Checklist
- Are all service-raised API-facing errors custom exceptions?
- Do all custom exceptions inherit from AppException lineage?
- Are status_code values semantically correct?
- Are error_code values explicit and stable?
- Is there any duplicated schema-level validation in service code?
- Are routers free from business exception translation?
- Are shared exceptions placed in service_exceptions.py?
- Are local exceptions kept inside each service domain file?

## Auto Audit Checklist
- No raw ValueError, RuntimeError, or generic Exception for API-facing flows.
- No direct business error handling outside service layer.
- Every raised custom error has logical status_code and explicit error_code.
- Every service error path is logged.
- Validation is not duplicated when schema already enforces it.
