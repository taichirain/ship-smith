from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .enums import DeployStrategy, HealthCheckType


class GitConfig(BaseModel):
    repo: str = Field(..., description="Git repository URL (HTTPS or SSH)")
    branch: str = Field(default="main", description="Default branch to deploy from")

    @field_validator("repo")
    @classmethod
    def repo_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("git.repo cannot be empty")
        return v


class DeployConfig(BaseModel):
    workdir: str = Field(..., description="Agent 执行部署命令的工作目录")
    strategy: DeployStrategy = Field(
        default=DeployStrategy.COMPOSE_BUILD,
        description="部署策略：compose-build 或 compose-pull",
    )


class ComposeConfig(BaseModel):
    file: str = Field(default="docker-compose.yml", description="Docker Compose 文件路径")
    service: str = Field(default="app", description="用于健康检查判定的主服务名")


class HealthCheckConfig(BaseModel):
    type: HealthCheckType = Field(default=HealthCheckType.HTTP, description="健康检查类型")
    url: Optional[str] = Field(default=None, description="HTTP 健康检查 URL")
    host: Optional[str] = Field(default=None, description="TCP 健康检查主机")
    port: Optional[int] = Field(default=None, description="TCP 健康检查端口")
    timeout_seconds: int = Field(default=10, ge=1, le=300, description="健康检查超时时间")
    expected_status: Optional[int] = Field(default=200, description="HTTP 期望状态码")

    @field_validator("url")
    @classmethod
    def http_requires_url(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("type") == HealthCheckType.HTTP and not v:
            raise ValueError("health_check.url is required when type is 'http'")
        return v

    @field_validator("port")
    @classmethod
    def tcp_requires_host_and_port(cls, v: Optional[int], info) -> Optional[int]:
        if info.data.get("type") == HealthCheckType.TCP:
            if not info.data.get("host") or not v:
                raise ValueError("health_check.host and health_check.port are required when type is 'tcp'")
        return v


class FlagsConfig(BaseModel):
    file: str = Field(..., description="Feature Flag 本地 JSON 文件路径")

    @field_validator("file")
    @classmethod
    def file_must_be_absolute(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("flags.file must be an absolute path")
        return v


class RuntimeConfig(BaseModel):
    env_file: Optional[str] = Field(default=None, description="环境变量文件路径，相对于 workdir")
    install_command: Optional[str] = Field(default=None, description="可选的安装命令")
    pre_deploy: Optional[str] = Field(default=None, description="部署前执行的命令")
    post_deploy: Optional[str] = Field(default=None, description="部署成功后执行的命令")


class ProjectConfig(BaseModel):
    """Future import/export format. Not used by the API or Agent at runtime."""

    project: str = Field(..., description="项目名称，仅用于标识")
    git: GitConfig
    deploy: DeployConfig
    compose: ComposeConfig = Field(default_factory=ComposeConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    flags: FlagsConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @field_validator("project")
    @classmethod
    def project_name_must_be_valid(cls, v: str) -> str:
        import re

        if not v.strip():
            raise ValueError("project name cannot be empty")
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError("project name can only contain alphanumeric chars, dots, dashes, and underscores")
        return v

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "ProjectConfig":
        import yaml
        from pydantic import ValidationError

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

        try:
            return cls.model_validate(data)
        except ValidationError as e:
            error_messages = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                error_messages.append(f"  - {loc}: {err['msg']}")
            raise ValueError(
                "Invalid shipsmith.yaml configuration:\n" + "\n".join(error_messages)
            )

    def to_yaml(self) -> str:
        import yaml

        data = self.model_dump(mode="json")
        return yaml.dump(data, sort_keys=False, default_flow_style=False)
