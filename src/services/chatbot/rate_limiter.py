import time
from typing import Tuple, Dict, Any

from integrations.redis_provider import RedisProvider
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class UserRateLimiter:

    def __init__(self, redis_provider: RedisProvider):
        self.redis = redis_provider

    async def check_and_increment(
        self,
        student_id: str,
        rpm_limit: int,
        daily_limit: int,
    ) -> Tuple[bool, str, Dict[str, Any]]:

        now = int(time.time())
        current_minute_bucket = now // 60
        today_date = time.strftime("%Y-%m-%d")

        rpm_key = f"ratelimit:rpm:{student_id}:{current_minute_bucket}"
        daily_key = f"ratelimit:daily:{student_id}:{today_date}"

        try:
            client = self.redis._ensure_client()
            pipe = client.pipeline()
            pipe.incr(rpm_key)
            pipe.expire(rpm_key, 65)
            pipe.incr(daily_key)
            pipe.expire(daily_key, 86400 * 2)
            results = await pipe.execute()

            minute_count = int(results[0])
            daily_count = int(results[2])

            if minute_count > rpm_limit:
                logger.warning(
                    "Rate limit exceeded (RPM) for student %s: %d/%d reqs/min",
                    student_id,
                    minute_count,
                    rpm_limit,
                )
                return (
                    False,
                    f"Too many requests in a short period. Your tier allows {rpm_limit} requests/minute. Please wait a moment.",
                    {
                        "limit_type": "rpm",
                        "current": minute_count,
                        "limit": rpm_limit,
                        "retry_after_seconds": 60 - (now % 60),
                    },
                )

            if daily_count > daily_limit:
                logger.warning(
                    "Daily limit exceeded for student %s: %d/%d reqs/day",
                    student_id,
                    daily_count,
                    daily_limit,
                )
                return (
                    False,
                    f"Daily request quota exceeded. Your tier allows {daily_limit} requests/day. Please upgrade your plan or return tomorrow.",
                    {
                        "limit_type": "daily",
                        "current": daily_count,
                        "limit": daily_limit,
                    },
                )

            return (
                True,
                "",
                {
                    "rpm_remaining": max(0, rpm_limit - minute_count),
                    "daily_remaining": max(0, daily_limit - daily_count),
                },
            )

        except Exception as exc:
            logger.error("Rate limiter encountered Redis error for student %s: %s", student_id, exc)
            raise RuntimeError(f"Rate limiting failed due to Redis error: {exc}") from exc
