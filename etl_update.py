import io
import os
import yadisk

from data_pipeline import (
    load_single_file,
    load_and_prepare_two_dataframes,
    prepare_dashboard_data,
    write_dashboard_to_postgres_append,
)

POSTGRES_URL = os.environ["POSTGRES_URL"]
YANDEX_TOKEN = os.environ["YANDEX_TOKEN"]
YANDEX_FILE_1 = os.environ["YANDEX_FILE_1"]
YANDEX_FILE_2 = os.environ["YANDEX_FILE_2"]


def download_file_to_memory(y, remote_path: str):
    buffer = io.BytesIO()
    y.download(remote_path, buffer)
    buffer.seek(0)
    return buffer


def main():
    y = yadisk.YaDisk(token=YANDEX_TOKEN)

    if not y.check_token():
        raise RuntimeError("Токен Яндекс Диска невалидный.")

    file1_obj = download_file_to_memory(y, YANDEX_FILE_1)
    file2_obj = download_file_to_memory(y, YANDEX_FILE_2)

    df_left = load_single_file(file1_obj, YANDEX_FILE_1)
    df_right = load_single_file(file2_obj, YANDEX_FILE_2)

    prepared_merge = load_and_prepare_two_dataframes(df_left, df_right)
    dashboard_df = prepare_dashboard_data(prepared_merge)

    inserted_rows = write_dashboard_to_postgres_append(
        dashboard_df,
        postgres_url=POSTGRES_URL,
        source="yadisk",
        file_names=f"{YANDEX_FILE_1} | {YANDEX_FILE_2}",
    )

    print(f"Данные успешно обновлены из Яндекс Диска. Добавлено новых строк: {inserted_rows}")


if __name__ == "__main__":
    main()
