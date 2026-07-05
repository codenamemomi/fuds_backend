from pydantic import BaseModel, ConfigDict


class AnalyticsSummaryRead(BaseModel):
    total_users: int = 0
    active_users: int = 0
    total_vendors: int = 0
    active_vendors: int = 0
    total_orders: int = 0
    completed_orders: int = 0
    total_revenue: float = 0.0
    shopping_lists_created: int = 0
    subscriptions_due_this_week: int = 0
    available_riders: int = 0
    registered_riders: int = 0

    model_config = ConfigDict(from_attributes=True)
