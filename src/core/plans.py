from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class PlanConfig:
    name: str
    rpm: int
    daily_limit: int
    monthly_budget_usd: float
    model_alias: str


PLANS: Dict[str, PlanConfig] = {
    "free": PlanConfig(
        name="Free",
        rpm=5,
        daily_limit=30,
        monthly_budget_usd=0.50,
        model_alias="eduhub/answering-free",
    ),
    "standard": PlanConfig(
        name="Standard",
        rpm=15,
        daily_limit=150,
        monthly_budget_usd=5.00,
        model_alias="eduhub/answering",
    ),
    "premium": PlanConfig(
        name="Premium",
        rpm=30,
        daily_limit=500,
        monthly_budget_usd=15.00,
        model_alias="eduhub/answering-premium",
    ),
}


def get_user_plan_config(plan_name: Optional[str]) -> PlanConfig:
    """Retrieve plan configuration. Defaults to 'free' if unspecified or unknown."""
    if not plan_name:
        return PLANS["free"]
    normalized = str(plan_name).lower().strip()
    return PLANS.get(normalized, PLANS["free"])
