from mplms.core.config import get_settings
from mplms.core.database import ensure_sqlite_data_dir
from mplms.core.database import is_postgresql
from mplms.core.database import is_sqlite


def main() -> None:
    settings = get_settings()
    ensure_sqlite_data_dir(settings.database_url)

    if is_sqlite(settings.database_url):
        storage = "SQLite (local dev)"
    elif is_postgresql(settings.database_url):
        storage = "PostgreSQL"
    else:
        storage = settings.database_url.split(":", 1)[0]

    print(f"MPLMS backend ready — {storage}.")


if __name__ == "__main__":
    main()
