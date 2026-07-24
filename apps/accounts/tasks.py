from celery import shared_task
import logging
from apps.accounts.services import KeycloakSyncService

logger = logging.getLogger(__name__)

@shared_task(name="accounts.sync_keycloak_users")
def sync_keycloak_users_task() -> dict:
    logger.info("Starting accounts.sync_keycloak_users celery task")
    try:
        result = KeycloakSyncService().sync_all()
        logger.info("Keycloak sync task completed successfully: %s", result)
        return result
    except Exception as exc:
        logger.error("Keycloak sync task failed: %s", exc)
        raise exc
