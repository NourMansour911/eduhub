---
name: mongo-repository-pattern
description: "Use when creating, modifying, or reviewing MongoDB repository classes in this project. Defines the Motor async repository pattern, collection bootstrapping, index initialization, and query encapsulation."
---

# MongoDB Repository Pattern Skill

## Purpose

Defines the canonical pattern for Motor-based async MongoDB repositories in this project — including the `create_instance` classmethod, `init_collection` bootstrapping, `get_indexes` declaration, and query method conventions. Grounded in `src/repositories/lecture_repo.py`, `student_persona_repo.py`, and `mongo_bootstrap.py`.

## When To Use

- Creating a new MongoDB repository class.
- Adding a new collection or index.
- Reviewing repository code for query encapsulation compliance.
- Adding the new repository to the application startup.

---

## Rule 1: Repository Class Structure

```python
# src/repositories/<domain>_repo.py
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import MyDomainModel
from enums import DBEnum


class MyDomainRepo:

    def __init__(self, db_client: AsyncIOMotorDatabase):
        self.db_client       = db_client
        self.collection_name = DBEnum.COLLECTION_MY_DOMAIN.value   # from enums
        self.collection      = self.db_client[self.collection_name]

    # --- Classmethod factory (required by mongo_bootstrap) ---
    @classmethod
    async def create_instance(cls, db_client: AsyncIOMotorDatabase):
        return cls(db_client)

    # --- Bootstrap: create collection + indexes if not present ---
    async def init_collection(self) -> None:
        existing = await self.db_client.list_collection_names()
        if self.collection_name not in existing:
            await self.db_client.create_collection(self.collection_name)
            for idx in self.get_indexes():
                await self.collection.create_index(
                    idx["key"],
                    name=idx.get("name"),
                    unique=idx.get("unique", False),
                )

    # --- Index declarations (classmethod — no instance needed) ---
    @classmethod
    def get_indexes(cls) -> list:
        return [
            {
                "key":    [("domain_id", 1)],
                "name":   "domain_id_index_1",
                "unique": True,
            },
            {
                "key":    [("course_id", 1)],
                "name":   "course_id_index_1",
                "unique": False,
            },
        ]

    # --- Query methods (all business queries live here) ---
    async def add_document(self, doc: MyDomainModel) -> str:
        result = await self.collection.insert_one(
            doc.model_dump(by_alias=True, exclude_none=True)
        )
        return str(result.inserted_id)

    async def get_by_id(self, domain_id: str) -> MyDomainModel | None:
        record = await self.collection.find_one({"domain_id": domain_id})
        return MyDomainModel(**record) if record else None

    async def delete_by_id(self, domain_id: str) -> int:
        result = await self.collection.delete_one({"domain_id": domain_id})
        return int(result.deleted_count)
```

---

## Rule 2: Collection Name Convention

Collection names are defined as enum values in `src/enums/db_enum.py`:

```python
class DBEnum(str, Enum):
    COLLECTION_LECTURE_NAME         = "lectures"
    COLLECTION_ANSWER_NAME          = "answers"
    COLLECTION_EVALUATION_NAME      = "evaluations"
    COLLECTION_STUDENT_PERSONA_NAME = "student_personas"
```

Repos reference `DBEnum.COLLECTION_<DOMAIN>.value` — never hardcode collection name strings in repo files.

---

## Rule 3: Bootstrap Registration

Register every new repo in `main.py`'s lifespan — pass it to `init_mongo_resources`:

```python
# main.py
from repositories.my_domain_repo import MyDomainRepo

# In lifespan:
mongo_repos = await init_mongo_resources(
    app.state.mongo_db,
    [AnswerRepo, LectureRepo, EvaluationRepo, StudentPersonaRepo, MyDomainRepo],  # ← add here
)
app.state.my_domain_repo = mongo_repos["MyDomainRepo"]
```

The `init_mongo_resources` bootstrap function handles all repos uniformly:

```python
async def init_mongo_resources(db_client, repo_classes):
    repo_instances = {}
    for repo_class in repo_classes:
        repo = await repo_class.create_instance(db_client)
        await repo.init_collection()
        repo_instances[repo_class.__name__] = repo
    return repo_instances
```

This means every repo class MUST implement `create_instance(db_client)` and `init_collection()`.

---

## Rule 4: Query Encapsulation

All MongoDB queries MUST live inside repository methods — never in service code:

```python
# CORRECT — query stays in repo
class LectureRepo:
    async def get_lectures_by_course(self, course_id: str) -> list[LectureModel]:
        cursor = self.collection.find({"course_id": course_id}).sort("order", 1)
        results = []
        async for doc in cursor:
            results.append(LectureModel(**doc))
        return results

# WRONG — service constructs raw query
class LectureService:
    async def get_lectures(self, course_id: str):
        cursor = self.lecture_repo.collection.find({"course_id": course_id})  # ← violates boundary
```

**Rules:**
- Services call repo methods by name — never access `repo.collection` directly.
- Repo methods return typed domain models (`LectureModel`, etc.) — never raw dicts.
- `find_one` → return `Model(**record) if record else None`.
- `find` (cursor) → iterate with `async for` and collect into a list before returning.
- Return types are always explicit: `-> ModelType | None` or `-> list[ModelType]`.

---

## Rule 5: Upsert Pattern

```python
async def upsert_document(self, domain_id: str, doc: MyDomainModel) -> None:
    await self.collection.update_one(
        {"domain_id": domain_id},
        {"$set": doc.model_dump(by_alias=True, exclude_none=True)},
        upsert=True,
    )
```

Use `upsert=True` when the document may or may not exist (e.g., persona documents per student).

---

## Review Checklist

- Does the repo class have `create_instance` and `init_collection` methods?
- Are collection names referenced via `DBEnum`, not hardcoded strings?
- Is the repo registered in `main.py`'s `init_mongo_resources` call?
- Are all MongoDB queries inside repo methods (not in services)?
- Do query methods return typed domain models (not raw dicts)?
- Does `find_one` return `Model(**record) if record else None`?
- Does `find` iterate with `async for` and return a list?
