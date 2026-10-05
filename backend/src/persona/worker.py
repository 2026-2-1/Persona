from celery import Celery

from persona.config import get_settings
from persona.execution import run_session

celery_app = Celery("persona", broker=get_settings().redis_url)
celery_app.conf.update(
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=3,
    task_publish_retry=False,
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
)


@celery_app.task(name="persona.execute_session")
def execute_session(session_id: str) -> None:
    run_session(session_id)


def publish_session(session_id: str) -> None:
    execute_session.apply_async(args=[session_id], retry=False)
