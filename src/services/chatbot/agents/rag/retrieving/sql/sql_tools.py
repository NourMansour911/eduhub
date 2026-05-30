class SQLTools:
	def __init__(self) -> None:
		pass


def get_sql_tools() -> SQLTools:
	return SQLTools()


__all__ = ["SQLTools", "get_sql_tools"]