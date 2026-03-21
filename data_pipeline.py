import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime

TTM_STAGES = [
    "Сбор данных",
    "Открыт",
    "Заблокирован",
    "На стороне менеджера",
    "Бэклог разработки",
    "В работе",
]
CYCLE_STAGES = ["Бэклог разработки", "В работе"]

REQUIRED_KEY_OPTIONS = [
    ("Ключ", "issue_key"),
    ("issue_key", "Ключ"),
]

COLS_TO_DROP = [
    "Статус",
    "Дата завершения",
    "DutyGPT prediction result",
    "Резолюция по ролям",
    "Причина блокировки",
    "Закрыт",
    "issue_key",
]


def get_engine(postgres_url: str):
    return sa.create_engine(postgres_url)


def load_single_file(file_obj, file_name: str):
    file_name_lower = file_name.lower()

    if file_name_lower.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif file_name_lower.endswith(".xlsx"):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError(f"Файл {file_name}: поддерживаются только CSV и XLSX.")

    df.columns = df.columns.astype(str).str.strip()
    return df


def validate_merge_keys(df_left, df_right):
    for left_key, right_key in REQUIRED_KEY_OPTIONS:
        if left_key in df_left.columns and right_key in df_right.columns:
            return left_key, right_key

    raise ValueError(
        "Не найдены ключи для объединения. "
        "В одном файле должна быть колонка 'Ключ', а в другом — 'issue_key'."
    )


def validate_key_matches(df_left, df_right, left_key, right_key):
    left_values = set(df_left[left_key].dropna().astype(str).str.strip())
    right_values = set(df_right[right_key].dropna().astype(str).str.strip())
    matches = left_values & right_values

    if not matches:
        raise ValueError(
            f"Колонки для объединения найдены ({left_key} и {right_key}), "
            "но совпадающих значений ключей между файлами нет."
        )


def clean_components(val):
    if pd.isna(val):
        return None

    comps = [c.strip() for c in str(val).split(",") if c.strip()]

    if len(comps) == 1 and comps[0] == "Запуск скрипта":
        return None

    if len(comps) >= 2:
        if "Запуск скрипта" in comps:
            comps.remove("Запуск скрипта")
            return comps[0] if len(comps) == 1 else None
        return None

    return val


def preprocess_merged_data(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all")

    if "Количество обращений" in df.columns:
        df["Количество обращений"] = df["Количество обращений"].fillna("1-4")

    if "Пинг-понг обращения" in df.columns:
        df["Пинг-понг обращения"] = df["Пинг-понг обращения"].fillna(1.0)

    df = df.drop(columns=COLS_TO_DROP, errors="ignore")

    if "Резолюция" in df.columns:
        df = df[~df["Резолюция"].isin(["Не будет исправлено", "Дубликат"])]

    if "Компоненты" in df.columns:
        df["Компоненты"] = df["Компоненты"].apply(clean_components)
        df = df.dropna(subset=["Компоненты"])

    df = df.reset_index(drop=True)
    return df


def merge_two_dataframes(df_left, df_right):
    left_key, right_key = validate_merge_keys(df_left, df_right)
    validate_key_matches(df_left, df_right, left_key, right_key)

    merged_df = pd.merge(
        df_left,
        df_right,
        left_on=left_key,
        right_on=right_key,
        how="left"
    )
    return merged_df


def load_and_prepare_two_dataframes(df_left, df_right):
    merged_df = merge_two_dataframes(df_left, df_right)
    prepared_df = preprocess_merged_data(merged_df)

    if prepared_df.empty:
        raise ValueError("После объединения и очистки не осталось данных.")

    return prepared_df


def prepare_dashboard_data(df_):
    df_ = df_.copy()

    if "Дата создания" not in df_.columns:
        raise ValueError("В данных нет колонки 'Дата создания'.")

    df_["Дата создания"] = pd.to_datetime(df_["Дата создания"], errors="coerce")
    df_ = df_.dropna(subset=["Дата создания"])

    for col in set(TTM_STAGES + CYCLE_STAGES):
        if col not in df_.columns:
            df_[col] = 0
        df_[col] = pd.to_numeric(df_[col], errors="coerce").fillna(0)

    df_["ttm_days"] = df_[TTM_STAGES].sum(axis=1) / 1440
    df_["cycle_time"] = df_[CYCLE_STAGES].sum(axis=1) / 1440
    df_["wait_time_days"] = (df_["ttm_days"] - df_["cycle_time"]).clip(lower=0)

    df_["Резолюция"] = df_.get("Резолюция", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Компоненты"] = df_.get("Компоненты", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Приоритет"] = df_.get("Приоритет", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Пинг-понг обращения"] = pd.to_numeric(df_.get("Пинг-понг обращения", 0), errors="coerce").fillna(0)
    df_["Количество обращений"] = df_.get("Количество обращений", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")

    if "Тип" not in df_.columns:
        df_["Тип"] = "Не указано"
    df_["Тип"] = df_["Тип"].fillna("Не указано").astype(str).str.strip()

    return df_


def normalize_key_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Ключ" not in df.columns:
        raise ValueError("В датафрейме нет колонки 'Ключ', по которой можно проверять дубликаты.")

    df["Ключ"] = df["Ключ"].astype(str).str.strip()
    df = df[df["Ключ"] != ""]
    df = df.dropna(subset=["Ключ"])
    df = df.drop_duplicates(subset=["Ключ"], keep="last")

    return df


def ensure_dashboard_table_exists(engine, df: pd.DataFrame):
    inspector = inspect(engine)
    if not inspector.has_table("dashboard_tasks"):
        df.head(0).to_sql("dashboard_tasks", engine, if_exists="fail", index=False)


def cleanup_existing_duplicates(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM dashboard_tasks a
            USING dashboard_tasks b
            WHERE a.ctid < b.ctid
              AND a."Ключ" = b."Ключ"
              AND a."Ключ" IS NOT NULL
        """))


def ensure_unique_constraint(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'dashboard_tasks_key_unique'
                ) THEN
                    ALTER TABLE dashboard_tasks
                    ADD CONSTRAINT dashboard_tasks_key_unique UNIQUE ("Ключ");
                END IF;
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END
            $$;
        """))


def write_dashboard_to_postgres_append(df, postgres_url: str, source: str, file_names: str = ""):
    engine = get_engine(postgres_url)

    df = normalize_key_column(df)
    ensure_dashboard_table_exists(engine, df)
    cleanup_existing_duplicates(engine)
    ensure_unique_constraint(engine)

    metadata = MetaData()
    dashboard_table = Table("dashboard_tasks", metadata, autoload_with=engine)

    records = df.to_dict(orient="records")
    inserted_rows = 0

    if records:
        stmt = pg_insert(dashboard_table).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["Ключ"])

        with engine.begin() as conn:
            result = conn.execute(stmt)
            inserted_rows = result.rowcount if result.rowcount is not None else 0

    meta_df = pd.DataFrame([
        {
            "updated_at": datetime.utcnow(),
            "source": source,
            "file_names": file_names,
            "rows_count_in_batch": len(df),
            "inserted_rows": inserted_rows,
        }
    ])
    meta_df.to_sql("dashboard_meta", engine, if_exists="replace", index=False)

    return inserted_rows


def read_dashboard_from_postgres(postgres_url: str):
    engine = get_engine(postgres_url)
    try:
        return pd.read_sql('SELECT * FROM dashboard_tasks', engine)
    except Exception:
        return pd.DataFrame()


def read_meta_from_postgres(postgres_url: str):
    engine = get_engine(postgres_url)
    try:
        return pd.read_sql('SELECT * FROM dashboard_meta', engine)
    except Exception:
        return pd.DataFrame()
