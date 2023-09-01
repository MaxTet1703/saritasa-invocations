import collections.abc
import dataclasses

import invoke


@dataclasses.dataclass
class SystemSettings:
    """Settings for system module."""

    settings_template: str = "config/settings/local.template.py"
    save_settings_from_template_to: str = "config/settings/local.py"
    vs_code_settings_template: str = ".vscode/recommended_settings.json"


@dataclasses.dataclass
class GitSettings:
    """Settings for git module."""

    merge_ff: str = "false"
    pull_ff: str = "only"


@dataclasses.dataclass
class PreCommitSettings:
    """Settings for pre-commit module."""

    hooks: collections.abc.Sequence[str] = (
        "pre-commit",
        "pre-push",
        "commit-msg",
    )


@dataclasses.dataclass
class PythonSettings:
    """Settings for python module."""

    entry: str = "python"
    docker_service: str = "web"
    docker_service_params: str = "--rm"


@dataclasses.dataclass
class DockerSettings:
    """Settings for docker module."""

    main_containers: collections.abc.Sequence[str] = (
        "postgres",
        "redis",
    )
    build_image_tag: str = ""
    buildpack_builder: str = "paketobuildpacks/builder:base"
    buildpack_runner: str = "paketobuildpacks/run:base"
    buildpack_requirements_path: str = "requirements"


@dataclasses.dataclass
class GitHubActionsSettings:
    """Settings for github actions module."""

    hosts: collections.abc.Sequence[str] = tuple()


@dataclasses.dataclass
class DjangoSettings:
    """Settings for django module."""

    runserver_command: str = "runserver_plus"
    runserver_host: str = "0.0.0.0"
    runserver_port: str = "8000"
    runserver_params: str = ""
    runserver_docker_params: str = "--rm --service-ports"
    migrate_command: str = "migrate"
    default_superuser_email: str = "root@localhost"
    default_superuser_username: str = "root"
    default_superuser_password: str = "root"
    shell_command: str = "shell_plus --ipython"
    path_to_remote_config_file: str = "/workspace/app/config/settings/.env"
    settings_path: str = "config.settings.local"
    remote_db_config_mapping: dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            "dbname": "RDS_DB_NAME",
            "host": "RDS_DB_HOST",
            "port": "RDS_DB_PORT",
            "username": "RDS_DB_USER",
            "password": "RDS_DB_PASSWORD",
        },
    )


@dataclasses.dataclass
class CelerySettings:
    """Settings for celery module."""

    service_name: str = "celery"
    local_cmd: str = (
        "celery --app config.celery:app "
        "worker --beat --scheduler=django --loglevel=info"
    )


@dataclasses.dataclass
class FastAPISettings:
    """Settings for fastapi module."""

    uvicorn_command: str = "-m uvicorn"
    app: str = "config:fastapi_app"
    host: str = "0.0.0.0"
    port: str = "8000"
    params: str = "--reload"
    docker_params: str = "--rm --service-ports"


@dataclasses.dataclass
class AlembicSettings:
    """Settings for alembic module."""

    command: str = "-m alembic"
    migrations_folder: str = "db/migrations/versions"
    adjust_messages: collections.abc.Sequence[str] = (
        "# ### commands auto generated by Alembic - please adjust! ###",
        "# ### end Alembic commands ###",
    )


@dataclasses.dataclass
class CruftSettings:
    """Settings for cruft module."""

    project_tmp_folder: str = ".tmp"


@dataclasses.dataclass
class DBSettings:
    """Settings for db module."""

    password_pattern: str = "Password.*"
    load_dump_command: str = (
        "psql "
        "{additional_params} "
        "--dbname={dbname} "
        "--host={host} "
        "--port={port} "
        "--username={username} "
        "--file={file}"
    )
    dump_filename: str = "local_db_dump.sql"
    load_additional_params: str = "--quiet"
    dump_command: str = (
        "pg_dump "
        "{additional_params} "
        "--dbname={dbname} "
        "--host={host} "
        "--port={port} "
        "--username={username} "
        "--file={file}"
    )
    dump_additional_params: str = "--no-owner"


# This mapping should not be filled manually. You just need create an instance
# of `K8SSettings` and it will be auto added to this mapping
_K8S_CONFIGS: dict[str, "K8SSettings"] = {}


class K8SSettingsMeta(type):
    """Meta class for K8SSettings."""

    def __call__(cls, *args, **kwargs) -> "K8SSettings":
        """Update mapping of environments."""
        instance: K8SSettings = super().__call__(*args, **kwargs)
        if instance.name in _K8S_CONFIGS:
            raise ValueError(f"{instance.name} config is already defined")
        _K8S_CONFIGS[instance.name] = instance
        return instance


@dataclasses.dataclass(frozen=True)
class K8SDBSettings:
    """Description of k8s db config."""

    namespace: str
    pod_selector: str
    dump_filename: str = ""
    password_pattern: str = "Password: "
    pod_command: str = (
        "kubectl get pods --namespace {db_pod_namespace} "
        "--selector={db_pod_selector} "
        "--output jsonpath='{{.items[0].metadata.name}}'"
    )
    exec_command: str = (
        "kubectl exec -ti --namespace {db_pod_namespace} " "$({db_pod})"
    )
    dump_command: str = (
        "pg_dump "
        "{additional_params} "
        "--dbname={dbname} "
        "--host={host} "
        "--port={port} "
        "--username={username} "
        "--file {file}"
    )
    dump_additional_params: str = "--no-owner"


@dataclasses.dataclass(frozen=True)
class K8SSettings(metaclass=K8SSettingsMeta):
    """Description of environment config."""

    name: str
    cluster: str
    proxy: str
    namespace: str
    db_config: K8SDBSettings
    port: str = "443"
    auth: str = "github"
    pod_label: str = "app.kubernetes.io/component"
    default_component: str = "backend"
    default_entry: str = "cnb/lifecycle/launcher bash"
    python_shell: str = "shell_plus"
    health_check: str = "health_check"
    env_color: str = "cyan"


@dataclasses.dataclass(frozen=True)
class Config:
    """Settings for saritasa invocations."""

    project_name: str = ""
    default_k8s_env: str = "dev"

    system: SystemSettings = dataclasses.field(
        default_factory=SystemSettings,
    )
    git: GitSettings = dataclasses.field(
        default_factory=GitSettings,
    )
    pre_commit: PreCommitSettings = dataclasses.field(
        default_factory=PreCommitSettings,
    )
    docker: DockerSettings = dataclasses.field(
        default_factory=DockerSettings,
    )
    python: PythonSettings = dataclasses.field(
        default_factory=PythonSettings,
    )
    github_actions: GitHubActionsSettings = dataclasses.field(
        default_factory=GitHubActionsSettings,
    )
    django: DjangoSettings = dataclasses.field(
        default_factory=DjangoSettings,
    )
    celery: CelerySettings = dataclasses.field(
        default_factory=CelerySettings,
    )
    fastapi: FastAPISettings = dataclasses.field(
        default_factory=FastAPISettings,
    )
    alembic: AlembicSettings = dataclasses.field(
        default_factory=AlembicSettings,
    )
    cruft: CruftSettings = dataclasses.field(
        default_factory=CruftSettings,
    )
    db: DBSettings = dataclasses.field(
        default_factory=DBSettings,
    )
    k8s_configs: dict[str, K8SSettings] = dataclasses.field(
        default_factory=lambda: _K8S_CONFIGS,
    )

    def __post_init__(self) -> None:
        """Set default values for settings that are dependant on others."""
        if not self.docker.build_image_tag:
            self.docker.build_image_tag = self.project_name

        if not self.github_actions.hosts:
            self.github_actions.hosts = self.docker.main_containers

    @classmethod
    def from_context(cls, context: invoke.Context) -> "Config":
        """Get config from invoke context."""
        return context.config.get(
            "saritasa_invocations",
            cls,
        )
