import argparse
import logging
import sys
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _create_db_session():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "packages", "db"))
    from shipsmith_db.engine import get_engine
    from sqlalchemy.orm import sessionmaker
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def cmd_cleanup(args):
    from .cleanup import (
        cleanup_all,
        cleanup_heartbeats,
        cleanup_deployment_logs,
        cleanup_webhook_deliveries,
    )

    db = _create_db_session()

    try:
        if args.all:
            results = cleanup_all(db)
            logger.info(f"Cleanup completed successfully!")
            logger.info(f"Total records deleted: {results['total_deleted']}")
            for result in results['cleanup_results']:
                logger.info(f"  {result['table']}: {result['deleted_count']} records")
            return 0
        else:
            deleted_count = 0
            if args.heartbeats:
                result = cleanup_heartbeats(db, args.retention_days)
                logger.info(f"Heartbeats: deleted {result['deleted_count']} records")
                deleted_count += result['deleted_count']
            if args.deployment_logs:
                result = cleanup_deployment_logs(db, args.retention_days)
                logger.info(f"Deployment logs: deleted {result['deleted_count']} records")
                deleted_count += result['deleted_count']
            if args.webhook_payloads:
                result = cleanup_webhook_deliveries(db, args.retention_days)
                logger.info(f"Webhook deliveries: deleted {result['deleted_count']} records")
                deleted_count += result['deleted_count']

            if not any([args.heartbeats, args.deployment_logs, args.webhook_payloads]):
                logger.warning("No cleanup type specified. Use --all or specific flags.")
                return 1

            logger.info(f"Cleanup completed. Total deleted: {deleted_count}")
            return 0
    finally:
        db.close()


def cmd_show_policies(args):
    from .config import get_settings
    settings = get_settings()

    logger.info("Current retention policies (days):")
    logger.info(f"  Heartbeats: {settings.heartbeat_retention_days}")
    logger.info(f"  Deployment logs: {settings.deployment_logs_retention_days}")
    logger.info(f"  Webhook payloads: {settings.webhook_payload_retention_days}")
    logger.info(f"  Notification deliveries: {settings.notification_deliveries_retention_days}")
    logger.info(f"  Flag audits: {settings.flag_audits_retention_days}")
    logger.info(f"  Project audits: {settings.project_audits_retention_days}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="ShipSmith API CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old historical data")
    cleanup_parser.add_argument("--all", action="store_true", help="Cleanup all historical data")
    cleanup_parser.add_argument("--heartbeats", action="store_true", help="Cleanup old heartbeats")
    cleanup_parser.add_argument("--deployment-logs", dest="deployment_logs", action="store_true", help="Cleanup old deployment logs")
    cleanup_parser.add_argument("--webhook-payloads", dest="webhook_payloads", action="store_true", help="Cleanup old webhook payloads")
    cleanup_parser.add_argument("--retention-days", dest="retention_days", type=int, default=None, help="Override default retention days")
    cleanup_parser.set_defaults(func=cmd_cleanup)

    policies_parser = subparsers.add_parser("policies", help="Show current retention policies")
    policies_parser.set_defaults(func=cmd_show_policies)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
