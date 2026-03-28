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
YANDEX_FOLDER_PATH = os.environ["YANDEX_FOLDER_PATH"]


def download_file_to_memory(y, remote_path: str):
    buffer = io.BytesIO()
    y.download(remote_path, buffer)
    buffer.seek(0)
    return buffer


def get_files_from_folder(y, folder_path: str):
    items = list(y.listdir(folder_path))
    return [item for item in items if not item.is_dir()]


def main():
    y = yadisk.YaDisk(token=YANDEX_TOKEN)

    if not y.check_token():
        raise RuntimeError("Токен Яндекс Диска невалидный.")

    files = get_files_from_folder(y, YANDEX_FOLDER_PATH)

    if not files:
        print("В папке нет файлов. Обновление не требуется.")
        return

    if len(files) != 2:
        raise RuntimeError(
            f"В папке должно быть ровно 2 файла. Сейчас найдено: {len(files)}"
        )

    file1, file2 = files

    file1_obj = download_file_to_memory(y, file1.path)
    file2_obj = download_file_to_memory(y, file2.path)

    df_left = load_single_file(file1_obj, file1.name)
    df_right = load_single_file(file2_obj, file2.name)

    prepared_merge = load_and_prepare_two_dataframes(df_left, df_right)
    dashboard_df = prepare_dashboard_data(prepared_merge)

    inserted_rows = write_dashboard_to_postgres_append(
        dashboard_df,
        postgres_url=POSTGRES_URL,
    )

    y.remove(file1.path, permanently=True)
    y.remove(file2.path, permanently=True)

    print(f"Готово. Добавлено новых строк: {inserted_rows}. Файлы удалены из папки.")


if __name__ == "__main__":
    main()
