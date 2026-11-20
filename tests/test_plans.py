import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.plans import get_user_plan_config, PLANS
from dtos.redis_session_dto import RedisSessionDTO
from schemas.session_schema import SessionRequest, UpdateUserPlanRequest, UpdateUserPlanResponse
from services.chatbot.rate_limiter import UserRateLimiter
from integrations.litellm_admin import LiteLLMAdminClient


def test_plan_configuration_retrieval():
    # Test valid plans
    free_plan = get_user_plan_config("free")
    assert free_plan.name == "Free"
    assert free_plan.rpm == 5
    assert free_plan.daily_limit == 30
    assert free_plan.monthly_budget_usd == 0.50

    standard_plan = get_user_plan_config("standard")
    assert standard_plan.name == "Standard"
    assert standard_plan.rpm == 15
    assert standard_plan.daily_limit == 150
    assert standard_plan.monthly_budget_usd == 5.00

    premium_plan = get_user_plan_config("PREMIUM")
    assert premium_plan.name == "Premium"
    assert premium_plan.rpm == 30
    assert premium_plan.daily_limit == 500
    assert premium_plan.monthly_budget_usd == 15.00

    # Test fallback to free on unknown or None
    assert get_user_plan_config(None).name == "Free"
    assert get_user_plan_config("").name == "Free"
    assert get_user_plan_config("non_existent_tier").name == "Free"


def test_session_dto_and_schema_defaults():
    # SessionRequest defaults to free
    req = SessionRequest(user_id="stu_1", session_id="sess_1")
    assert req.plan == "free"

    req_custom = SessionRequest(user_id="stu_1", session_id="sess_1", plan="premium")
    assert req_custom.plan == "premium"

    # RedisSessionDTO defaults to free
    dto = RedisSessionDTO(user_id="stu_1")
    assert dto.plan == "free"

    dto_custom = RedisSessionDTO(user_id="stu_1", plan="standard")
    assert dto_custom.plan == "standard"


@pytest.mark.asyncio
async def test_rate_limiter_rpm_and_daily():
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_pipe = MagicMock()

    mock_redis._ensure_client.return_value = mock_client
    mock_client.pipeline.return_value = mock_pipe

    # First test: under limits (minute_count=3, daily_count=10)
    mock_pipe.execute = AsyncMock(return_value=[3, True, 10, True])
    limiter = UserRateLimiter(redis_provider=mock_redis)

    allowed, reason, meta = await limiter.check_and_increment("stu_test", rpm_limit=5, daily_limit=30)
    assert allowed is True
    assert reason == ""
    assert meta["rpm_remaining"] == 2
    assert meta["daily_remaining"] == 20

    # Second test: exceeding RPM (minute_count=6 > 5)
    mock_pipe.execute = AsyncMock(return_value=[6, True, 10, True])
    allowed, reason, meta = await limiter.check_and_increment("stu_test", rpm_limit=5, daily_limit=30)
    assert allowed is False
    assert "Too many requests" in reason
    assert meta["limit_type"] == "rpm"

    # Third test: exceeding Daily Limit (minute_count=1, daily_count=35 > 30)
    mock_pipe.execute = AsyncMock(return_value=[1, True, 35, True])
    allowed, reason, meta = await limiter.check_and_increment("stu_test", rpm_limit=5, daily_limit=30)
    assert allowed is False
    assert "Daily request quota exceeded" in reason
    assert meta["limit_type"] == "daily"


@pytest.mark.asyncio
async def test_litellm_admin_client_sync():
    client = LiteLLMAdminClient(base_url="http://mock-litellm:4000", master_key="test-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        success = await client.sync_user_budget("stu_123", "premium")
        assert success is True

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["user_id"] == "stu_123"
        assert call_kwargs["json"]["max_budget"] == 15.00
        assert call_kwargs["json"]["budget_duration"] == "1mo"
        assert call_kwargs["json"]["rpm_limit"] == 30


@pytest.mark.asyncio
async def test_update_user_sessions_plan_in_redis():
    mock_redis = MagicMock()
    mock_client = MagicMock()
    mock_redis._ensure_client.return_value = mock_client
    mock_client.keys = AsyncMock(return_value=["user:stu_1:session:sess_1", "user:stu_1:session:sess_2"])

    mock_redis.get = AsyncMock(side_effect=[
        '{"user_id": "stu_1", "plan": "free", "messages": []}',
        '{"user_id": "stu_1", "plan": "free", "messages": []}'
    ])
    mock_redis.set = AsyncMock()

    from integrations.redis_provider import RedisProvider
    updated = await RedisProvider.update_user_sessions_plan(mock_redis, user_id="stu_1", plan="premium")
    assert updated == 2
    assert mock_redis.set.call_count == 2


@pytest.mark.asyncio
async def test_check_user_budget_preflight():
    client = LiteLLMAdminClient(base_url="http://mock-litellm:4000", master_key="test-key")

    # Case 1: user has remaining budget
    with patch.object(client, "get_user_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"user_id": "stu_1", "spend": 2.50, "max_budget": 5.00}
        has_budget, spend, max_b = await client.check_user_budget("stu_1")
        assert has_budget is True
        assert spend == 2.50
        assert max_b == 5.00

    # Case 2: user budget exhausted (Hard Block triggered)
    with patch.object(client, "get_user_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"user_id": "stu_1", "spend": 5.01, "max_budget": 5.00}
        has_budget, spend, max_b = await client.check_user_budget("stu_1")
        assert has_budget is False
        assert spend == 5.01
        assert max_b == 5.00

