APP_NAME=eduhub
APP_VERSION=0.1

STORAGE_PATH=storage

AZURE_DOC_ENDPOINT=
AZURE_DOC_KEY=

MONGO_DB_NAME =eduhub
MONGODB_URL=
QDRANT_URL=
REDIS_URL=

DB_BASE_URL=

COHERE_API_KEY=
OPENAI_API_URL=http://litellm:4000/v1

HF_TOKEN=

# LiteLLM Master Key (acts as OPENAI_API_KEY for the application)
OPENAI_API_KEY=sk-eduhub-litellm-master-secret-key-2026

LANGSMITH_API_KEY=
LANGSMITH_WORKSPACE=nourmansour
PROMPT_ENVIRONMENT_TAG=production
PROMPT_FETCH_REMOTE=true

GENERATION_BACKEND=OPENAI
GENERATION_MODEL_ID=deepseek/deepseek-v4-flash
# GENERATION_MODEL_ID=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

# Per-Node Virtual Model Routing (LiteLLM aliases)
ORCHESTRATOR_MODEL_ID=eduhub/router
ANSWERING_MODEL_ID=eduhub/answering
PLANNER_MODEL_ID=eduhub/planner
REFLECTION_MODEL_ID=eduhub/reflection
SUMMARY_MODEL_ID=eduhub/summary
PERSONA_MODEL_ID=eduhub/persona
GRADING_MODEL_ID=eduhub/grading
REWRITER_MODEL_ID=eduhub/rewriter


EMBEDDING_BACKEND=HF
# EMBEDDING_MODEL_ID=BAAI/bge-base-en-v1.5
EMBEDDING_MODEL_ID=intfloat/multilingual-e5-base
EMBEDDING_MODEL_SIZE=768


VECTOR_DB_BACKEND=QDRANT
VECTOR_DB_DISTANCE_METHOD=cosine