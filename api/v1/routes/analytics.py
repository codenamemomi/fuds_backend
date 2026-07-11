import csv
import io
from datetime import datetime
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload

from api.db.session import get_db
from api.v1.models.order import Order
from api.v1.schema.analytics import AnalyticsSummaryRead
from api.v1.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryRead)
def get_analytics_summary(db: Session = Depends(get_db)):
    """Retrieve the updated analytics summary."""
    service = AnalyticsService(db)
    return service.get_summary()


@router.get("/export")
def export_revenue_to_csv(db: Session = Depends(get_db)):
    """
    Export all orders to a CSV file to show revenue details per order per day.
    Can be imported directly into Excel.
    """
    orders = (
        db.query(Order)
        .options(joinedload(Order.user), joinedload(Order.vendor))
        .order_by(Order.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header reflecting order details, date, and revenue
    writer.writerow(["Order ID", "Date", "Status", "Revenue", "Vendor", "Customer"])

    for order in orders:
        date_str = order.created_at.strftime("%Y-%m-%d") if order.created_at else ""
        customer_name = (
            f"{order.user.first_name} {order.user.last_name}"
            if order.user and (order.user.first_name or order.user.last_name)
            else (order.user.email if order.user else f"User #{order.user_id}")
        )
        vendor_name = order.vendor.business_name if order.vendor else "Multi-Vendor / Platform"
        
        writer.writerow(
            [
                order.id,
                date_str,
                order.status,
                float(order.total_price),
                vendor_name,
                customer_name,
            ]
        )

    output.seek(0)
    filename = f"fuds_order_revenue_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)
