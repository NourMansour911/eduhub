from typing import Optional, Dict, Any, Tuple
import httpx

from core.plans import get_user_plan_config
from helpers.logger import get_integrations_logger

logger = get_integrations_logger(__name__)


class LiteLLMAdminClient:
   

    def __init__(self, base_url: str, master_key: str):
        self.base_url = base_url.rstrip("/")
        self.master_key = master_key
        self.headers = {
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        }

    async def sync_user_budget(self, user_id: str, plan_name: str) -> bool:

        plan = get_user_plan_config(plan_name)
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "max_budget": plan.monthly_budget_usd,
            "budget_duration": "1mo",
            "rpm_limit": plan.rpm,
        }

        url = f"{self.base_url}/end_user/new"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, json=payload, headers=self.headers)
                if res.status_code in (200, 201):
                    logger.info(
                        "LiteLLM budget synced for user '%s': plan=%s, max_budget=$%.2f/1mo, rpm=%d",
                        user_id,
                        plan.name,
                        plan.monthly_budget_usd,
                        plan.rpm,
                    )
                    return True
                logger.warning(
                    "LiteLLM budget sync returned status %d for user '%s': %s",
                    res.status_code,
                    user_id,
                    res.text,
                )
                return False
        except Exception as exc:
            logger.error("Failed to sync user budget with LiteLLM at %s: %s", url, exc)
            return False

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        
        url = f"{self.base_url}/end_user/info"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url, params={"end_user_id": user_id}, headers=self.headers)
                if res.status_code == 200:
                    return res.json()
                logger.warning("LiteLLM get_user_info returned status %d for user '%s': %s", res.status_code, user_id, res.text)
                return None
        except Exception as exc:
            logger.error("Failed to query LiteLLM user info for '%s': %s", user_id, exc)
            return None

    async def check_user_budget(self, user_id: str) -> Tuple[bool, float, float]:

        info = await self.get_user_info(user_id)
        if not info:
            return True, 0.0, 0.0

        spend = float(info.get("spend") or 0.0)
        max_budget = info.get("max_budget")

        if max_budget is not None:
            max_b = float(max_budget)
            if max_b > 0 and spend >= max_b:
                logger.warning(
                    "User '%s' budget exhausted: spend=$%.4f >= max_budget=$%.2f",
                    user_id,
                    spend,
                    max_b,
                )
                return False, spend, max_b
            return True, spend, max_b

        return True, spend, 0.0

