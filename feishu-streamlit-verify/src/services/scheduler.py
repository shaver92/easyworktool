from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date

from src.services.borrow_service import BorrowService
from src.services.notify_service import NotifyService


def start_scheduler(borrow_service: BorrowService, notify_service: NotifyService, cfg: dict) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=cfg["app"].get("timezone", "Asia/Shanghai"))

    def daily_scan_job() -> None:
        orders = borrow_service.list_due_and_overdue(cfg["notify"].get("days_before_due", 3))
        for order in orders:
            due_date = date.fromisoformat(order["due_at"])
            notify_type = "overdue" if due_date < date.today() else "due_soon"
            notify_service.enqueue_due_notice(order, notify_type=notify_type)
        notify_service.dispatch_pending()

    scheduler.add_job(
        daily_scan_job,
        "interval",
        hours=cfg["notify"].get("overdue_every_hours", 24),
        id="scan_due_orders",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
