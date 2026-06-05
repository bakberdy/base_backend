from sqlalchemy import create_engine, inspect, text

from app.core.database import _ensure_user_profiles_phone_columns


def test_ensure_user_profiles_phone_columns_adds_legacy_missing_columns() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE user_profiles (
                    user_id CHAR(32) PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    avatar_url TEXT,
                    avatar_object_key VARCHAR(512),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    completed_at DATETIME
                )
                """,
            ),
        )

        _ensure_user_profiles_phone_columns(connection)

        columns = {column["name"] for column in inspect(connection).get_columns("user_profiles")}
        assert {"country_code", "dial_code", "phone_number"}.issubset(columns)
