import collections.abc
import os

import invoke

from . import _config, db, db_k8s, docker, k8s, printing, python, system


def wait_for_database(context: invoke.Context) -> None:
    """Ensure that database is up and ready to accept connections.

    Function called just once during subsequent calls of management commands.

    Requires django_probes:
        https://github.com/painless-software/django-probes#basic-usage

    """
    if hasattr(wait_for_database, "_called"):
        return
    docker.up(context)
    # Not using manage to avoid infinite loop
    python.run(
        context,
        command="manage.py wait_for_database --stable 0",
    )
    wait_for_database._called = True


@invoke.task
def manage(
    context: invoke.Context,
    command: str,
    docker_params: str | None = None,
    watchers: collections.abc.Sequence[invoke.StreamWatcher] = (),
) -> None:
    """Run `manage.py` command.

    This command also handle starting of required services and waiting DB to
    be ready.

    Args:
        context: Invoke context
        command: Manage command
        docker_params: Params for docker run
        watchers: Automated responders to command

    """
    wait_for_database(context)
    python.run(
        context,
        docker_params=docker_params,
        command=f"manage.py {command}",
        watchers=watchers,
    )


@invoke.task
def makemigrations(context: invoke.Context) -> None:
    """Run makemigrations command and chown created migrations."""
    printing.print_success("Django: Make migrations")
    manage(context, command="makemigrations")
    if python.get_python_env() == python.PythonEnv.DOCKER:
        system.chown(context)


@invoke.task
def check_new_migrations(context: invoke.Context) -> None:
    """Check if there is new migrations or not."""
    printing.print_success("Django: Checking migrations")
    manage(
        context,
        command="makemigrations --check --dry-run",
    )


@invoke.task
def migrate(context: invoke.Context) -> None:
    """Run `migrate` command."""
    printing.print_success("Django: Apply migrations")
    config = _config.Config.from_context(context)
    manage(context, command=config.django.migrate_command)


@invoke.task
def resetdb(
    context: invoke.Context,
    apply_migrations: bool = True,
) -> None:
    """Reset database to initial state (including test DB).

    Requires django-extensions:
        https://django-extensions.readthedocs.io/en/latest/installation_instructions.html

    """
    printing.print_success("Reset database to its initial state")
    manage(context, command="drop_test_database --noinput")
    manage(context, command="reset_db -c --noinput")
    if not apply_migrations:
        return
    makemigrations(context)
    migrate(context)
    createsuperuser(context)
    set_default_site(context)


@invoke.task
def createsuperuser(
    context: invoke.Context,
    email: str = "",
    username: str = "",
    password: str = "",
) -> None:
    """Create superuser."""
    printing.print_success("Django: Create superuser")
    config = _config.Config.from_context(context)
    responder_email = invoke.FailingResponder(
        pattern=r"Email address: ",
        response=(email or config.django.default_superuser_email) + "\n",
        sentinel="That Email address is already taken.",
    )
    responder_user_name = invoke.Responder(
        pattern=r"Username: ",
        response=(username or config.django.default_superuser_username) + "\n",
    )
    responder_password = invoke.Responder(
        pattern=r"(Password: )|(Password \(again\): )",
        response=(password or config.django.default_superuser_password) + "\n",
    )

    try:
        manage(
            context,
            command="createsuperuser",
            watchers=(
                responder_email,
                responder_user_name,
                responder_password,
            ),
        )
    except invoke.Failure:
        printing.print_warn(
            "Superuser with that email already exists. Skipped.",
        )


@invoke.task
def run(context: invoke.Context) -> None:
    """Run development web-server."""
    printing.print_success("Running app")
    config = _config.Config.from_context(context)
    manage(
        context,
        docker_params=config.django.runserver_docker_params,
        command="{command} {host}:{port} {params}".format(
            command=config.django.runserver_command,
            host=config.django.runserver_host,
            port=config.django.runserver_port,
            params=config.django.runserver_params,
        ),
    )


@invoke.task
def shell(
    context: invoke.Context,
    params: str = "",
) -> None:
    """Shortcut for manage.py shell command.

    Requires django-extensions:
        https://django-extensions.readthedocs.io/en/latest/installation_instructions.html

    Additional params available here:
        https://django-extensions.readthedocs.io/en/latest/shell_plus.html

    """
    printing.print_success("Entering Django Shell")
    config = _config.Config.from_context(context)
    manage(
        context,
        command=f"{config.django.shell_command} {params}",
    )


@invoke.task
def dbshell(context: invoke.Context) -> None:
    """Open database shell with credentials from either local or dev env."""
    printing.print_success("Entering DB shell")
    manage(context, command="dbshell")


def set_default_site(context: invoke.Context) -> None:
    """Set default site to localhost.

    Set default site domain to `localhost:8000` so `get_absolute_url` works
    correctly in local environment

    """
    manage(
        context,
        command=(
            "set_default_site --name localhost:8000 --domain localhost:8000"
        ),
    )


@invoke.task
def load_db_dump(context: invoke.Context, file: str = "") -> None:
    """Reset db and load db dump."""
    resetdb(context, apply_migrations=False)
    db.load_db_dump(
        context,
        file=file,
        **load_django_db_settings(context),
    )


@invoke.task
def backup_local_db(
    context: invoke.Context,
    file: str = "",
) -> None:
    """Back up local db."""
    db.backup_local_db(
        context,
        file=file,
        **load_django_db_settings(context),
    )


@invoke.task
def backup_remote_db(
    context: invoke.Context,
    file: str = "",
) -> str:
    """Make dump of remote db and download it."""
    settings = load_django_remote_env_db_settings(context)
    db_k8s.create_dump(context, file=file, **settings)
    return db_k8s.get_dump(context, file=file)


@invoke.task
def load_remote_db(
    context: invoke.Context,
    file: str = "",
) -> None:
    """Make dump of remote db, download it and apply it."""
    file = backup_remote_db(context, file=file)
    load_db_dump(context, file=file)


def load_django_db_settings(context: invoke.Context) -> dict[str, str]:
    """Load django settings from settings file (DJANGO_SETTINGS_MODULE)."""
    config = _config.Config.from_context(context)
    os.environ["DJANGO_SETTINGS_MODULE"] = config.django.settings_path

    from django.conf import settings

    db_settings = settings.DATABASES["default"]
    return {
        "dbname": db_settings["NAME"],
        "host": db_settings["HOST"],
        "port": db_settings["PORT"],
        "username": str(db_settings["USER"]),
        "password": db_settings["PASSWORD"],
    }


def load_django_remote_env_db_settings(
    context: invoke.Context,
) -> dict[str, str]:
    """Load remote django settings from .env file.

    Requires python-decouple:
        https://github.com/HBNetwork/python-decouple

    """
    system.create_tmp_folder(context)
    env_path = ".tmp/.env.tmp"
    config = _config.Config.from_context(context)
    k8s.download_file(
        context,
        path_to_file_in_pod=config.django.path_to_remote_config_file,
        path_to_where_save_file=env_path,
    )

    # decouple could not be installed during project init
    # so we import decouple this way because it may not be installed
    # at the project initialization stage

    import decouple

    env_config = decouple.Config(decouple.RepositoryEnv(env_path))
    context.run(f"rm {env_path}")
    return {
        arg: str(env_config(env_var))
        for arg, env_var in config.django.remote_db_config_mapping.items()
    }
