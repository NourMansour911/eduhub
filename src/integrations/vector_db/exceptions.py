from core.app_exceptions import AppException


class VectorDBException(AppException):
    """Base exception for all vector DB errors."""
    def __init__(self, message="Vector DB error", details=None,status_code=500):
        super().__init__(
            message=message,
            status_code=status_code,  
            error_code="VDB_ERROR",
            details=details
        )


#  Connection 
class VectorDBConnectionError(VectorDBException):
    """Raised when the DB connection fails."""
    def __init__(self, db_path=None):
        details = {"db_path": db_path}
        super().__init__(
            message="Failed to connect to Vector DB",
            status_code = 503,
            details=details
        )
        


#  Collection 
class VectorDBCollectionNotFoundError(VectorDBException):
    """Raised when a requested collection does not exist."""
    def __init__(self, collection_name=None):
        details = {"collection_name": collection_name}
        super().__init__(
            message=f"Collection not found: {collection_name}",
            status_code = 404  ,
            details=details
        )


#  Insert 
class VectorDBInsertError(VectorDBException):
    """Raised when inserting a point fails."""
    def __init__(self, record_id=None):
        details = {"record_id": record_id}
        super().__init__(
            message="Failed to insert record into Vector DB",
            details=details
            
        )


class VectorDBBatchInsertError(VectorDBException):
    """Raised when inserting a batch of points fails."""
    def __init__(self, batch_size=None):
        details = {"batch_size": batch_size}
        super().__init__(
            message="Failed to insert batch into Vector DB",
            details=details
        )
        


#  Fetch 
class VectorDBFetchError(VectorDBException):
    """Raised when fetching points/chunks fails."""
    def __init__(self, collection_name=None):
        details = {"collection_name": collection_name}
        super().__init__(
            message="Failed to fetch data from Vector DB",
            details=details
        )
        


#  Search 
class VectorDBSearchError(VectorDBException):
    """Raised when search (vector or keyword) fails."""
    def __init__(self, collection_name=None, query=None):
        details = {"collection_name": collection_name, "query": query}
        super().__init__(
            message="Vector DB search failed",
            details=details
        )
        