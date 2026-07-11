from dataclasses import dataclass, field


@dataclass
class AnalyticsSummary:
    total_users: int = 0
    active_users: int = 0
    total_vendors: int = 0
    active_vendors: int = 0
    total_orders: int = 0
    revenue: float = 0.0
    shopping_lists_created: int = 0
    shopping_lists_due: list = field(default_factory=list)
    available_riders: int = 0
    registered_riders: int = 0

