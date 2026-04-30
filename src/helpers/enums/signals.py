from enum import Enum

class Signals(Enum):
    FILE_SIZE_EXCEEDED = "File Size Exceeded"
    FILE_TYPE_NOT_ALLOWED = "File Type Not Allowed"
    FILE_UPLOAD_SUCCESS = "File Uploaded Successfully"
    FILE_UPLOAD_FAILED = "File Upload Failed"
    FILE_NOT_FOUND = "File Not Found, Please Upload File"
    FILE_VALID = "File Validated Successfully"
    FILE_INVALID = "File Is Invalid"
    PROCESS_FAILED = "File Process Failed"
    
    FILE_FETCH_FAILED = "File Fetch Failed"
    NO_FILES_FETCHED = "No files found for chunking"
    
    CHUNKING_SUCCESS = "Chunk Processed Successfully"
    CHUNKING_FAILED = "Chunk Process Failed"
    CHUNK_RESET_SUCCESS = "Chunks Reset Successfully"
    NO_CHUNKS_FETCHED = "No CHUNKS found for chunking"
    
    CHUNK_VECTORIZE_SUCCESS = "Chunks Vectorized Successfully"
    CHUNK_VECTORIZE_FAILED = "Chunks Vectorize Failed"

    QUERY_VECTORIZE_FAILED = "Query Vectorize Failed"
    