from pydantic import BaseModel, ConfigDict
from api.v1.schema.marketplace import MarketplaceRead


class AnalyticsSummaryRead(BaseModel):
    total_users: int = 0
    active_users: int = 0
    total_vendors: int = 0
    active_vendors: int = 0
    total_orders: int = 0
    revenue: float = 0.0
    shopping_lists_created: int = 0
    shopping_lists_due: list[MarketplaceRead] = []
    available_riders: int = 0
    registered_riders: int = 0

    model_config = ConfigDict(from_attributes=True)

