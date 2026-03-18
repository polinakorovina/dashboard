import pandas as pd

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

def load_single_file(uploaded_file):
    if uploaded_file is None:
        return None, "Файл не загружен."

    try:
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif file_name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            return None, f"Файл {uploaded_file.name}: поддерживаются только CSV и XLSX."

        return df, None

    except Exception as e:
        return None, f"Ошибка при чтении файла {uploaded_file.name}: {e}"

def validate_two_files(uploaded_files):
    if uploaded_files is None or len(uploaded_files) != 2:
        return "Нужно загрузить ровно 2 файла."
    return None

def validate_merge_keys(df_left, df_right):
    for left_key, right_key in REQUIRED_KEY_OPTIONS:
        if left_key in df_left.columns and right_key in df_right.columns:
            return (left_key, right_key), None

    return None, (
        "Не найдены ключи для объединения. "
        "В одном файле должна быть колонка 'Ключ', а в другом — 'issue_key'."
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
    df.columns = df.columns.str.strip()
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
    merge_keys, error = validate_merge_keys(df_left, df_right)
    if error:
        return None, error

    left_key, right_key = merge_keys

    merged_df = pd.merge(
        df_left,
        df_right,
        left_on=left_key,
        right_on=right_key,
        how="left"
    )

    return merged_df, None

def load_and_prepare_two_files(uploaded_files):
    files_error = validate_two_files(uploaded_files)
    if files_error:
        return None, files_error

    df_left, error_left = load_single_file(uploaded_files[0])
    if error_left:
        return None, error_left

    df_right, error_right = load_single_file(uploaded_files[1])
    if error_right:
        return None, error_right

    merged_df, merge_error = merge_two_dataframes(df_left, df_right)
    if merge_error:
        return None, merge_error

    prepared_df = preprocess_merged_data(merged_df)

    if prepared_df.empty:
        return None, "После объединения и очистки не осталось данных."

    return prepared_df, None
