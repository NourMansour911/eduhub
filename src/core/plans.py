from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class PlanConfig:
    name: str
    rpm: int
    daily_limit: int
    monthly_budget_usd: float
    model_alias: str
    max_uploaded_lectures: int = 10
    allow_advanced_persona: bool = False


PLANS: Dict[str, PlanConfig] = {
    "free": PlanConfig(
        name="Free",
        rpm=5,
        daily_limit=30,
        monthly_budget_usd=0.50,
        model_alias="eduhub/answering-free",
        max_uploaded_lectures=3,
        allow_advanced_persona=False,
    ),
    "standard": PlanConfig(
        name="Standard",
        rpm=15,
        daily_limit=150,
        monthly_budget_usd=5.00,
        model_alias="eduhub/answering",
        max_uploaded_lectures=15,
        allow_advanced_persona=True,
    ),
    "premium": PlanConfig(
        name="Premium",
        rpm=30,
        daily_limit=500,
        monthly_budget_usd=15.00,
        model_alias="eduhub/answering-premium",
        max_uploaded_lectures=100,
        allow_advanced_persona=True,
    ),
}


def get_user_plan_config(plan_name: Optional[str]) -> PlanConfig:
    """Retrieve plan configuration. Defaults to 'free' if unspecified or unknown."""
    if not plan_name:
        return PLANS["free"]
    normalized = str(plan_name).lower().strip()
    return PLANS.get(normalized, PLANS["free"])
