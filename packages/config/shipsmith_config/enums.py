from enum import Enum


class DeployStrategy(str, Enum):
    COMPOSE_BUILD = "compose-build"
    COMPOSE_PULL = "compose-pull"


class DeployStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    SKIPPED = "skipped"


class HealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class TaskKind(str, Enum):
    DEPLOY = "deploy"
    ROLLBACK = "rollback"


class DeployMode(str, Enum):
    ALL_AT_ONCE = "all-at-once"
    ROLLING = "rolling"


class TriggerSource(str, Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    ROLLBACK = "rollback"


class HealthCheckType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    NONE = "none"


class ErrorCode(str, Enum):
    GIT_FETCH_FAILED = "git_fetch_failed"
    GIT_CHECKOUT_FAILED = "git_checkout_failed"
    GIT_RESET_FAILED = "git_reset_failed"
    DOCKER_BUILD_FAILED = "docker_build_failed"
    DOCKER_PULL_FAILED = "docker_pull_failed"
    DOCKER_UP_FAILED = "docker_up_failed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    AGENT_DISCONNECTED = "agent_disconnected"
    CONFIG_LOAD_FAILED = "config_load_failed"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN_ERROR = "unknown_error"
