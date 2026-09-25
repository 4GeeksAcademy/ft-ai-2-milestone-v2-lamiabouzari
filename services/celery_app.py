"""Celery application configuration for independent background workers."""

from celery import Celery

from config import settings

celery_app = Celery("ft_ai_tasks", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_track_started=True,
    result_expires=86400,
    task_time_limit=300,
    task_soft_time_limit=240,
    imports=("tasks.pipeline_tasks",),
)
