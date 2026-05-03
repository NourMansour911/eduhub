from collections.abc import Iterable
from typing import Any


async def init_mongo_resources(db_client: object, repo_classes: Iterable[type[Any]]) -> dict[str, Any]:
    repo_instances: dict[str, Any] = {}

    for repo_class in repo_classes:
        repo = await repo_class.create_instance(db_client)
        await repo.init_collection()
        repo_instances[repo_class.__name__] = repo

    return repo_instances