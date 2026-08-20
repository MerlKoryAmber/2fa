from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("mfa", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.imports = ("app.tasks",)
celery_app.conf.timezone = "Europe/Moscow"
# default = LDAP sync и прочее; otp = ExpressMS / Telegram (отдельный контейнер worker-otp)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {
    "app.tasks.send_expressms_otp": {"queue": "otp"},
    "app.tasks.send_telegram_otp": {"queue": "otp"},
    "app.tasks.sync_ldap_users": {"queue": "default"},
}
celery_app.conf.beat_schedule = {
    "ldap-sync-every-30m": {
        "task": "app.tasks.sync_ldap_users",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
}
