import pandas as pd
import psycopg2
import yadisk
import io
import os
import sqlite3

# Авторизация на Яндекс.Диске
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)

# Функция для обработки данных и добавления в PostgreSQL
def process():
    input_path = "/Data/Input"
    archive_path = "/Data/Archive"
    db_file_path = "/Data/my_database.db"  # Мы больше не используем локальный файл

    try:
        items = list(y.listdir(input_path))
    except Exception:
        print("Папка не найдена.")
        return

    files = [item for item in items if item.type == 'file']
    if len(files) < 2:
        print("Нужно 2 файла.")
        return

    # Загружаем файлы
    dfs = []
    for f_item in files[:2]:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            df = pd.read_csv(buf) if f_item.name.endswith('.csv') else pd.read_excel(buf)
            dfs.append(df)

    # Объединение файлов
    df_left, df_right = dfs[0], dfs[1]
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else: 
        print("Не найдены ключи объединения.")
        return

    # Очистка данных
    cols_to_drop = ['Приоритет', 'Статус', 'Дата завершения', 'DutyGPT prediction result', 
                    'Резолюция по ролям', 'Причина блокировки', 'Закрыт', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    if 'Резолюция' in merged_df.columns:
        merged_df = merged_df[~merged_df['Резолюция'].isin(['Не будет исправлено', 'Дубликат'])]

    # Соединяем с PostgreSQL
    conn = psycopg2.connect(
        dbname="my_database",  # Подключаемся к базе данных PostgreSQL
        user="your_user",
        password="your_password",
        host="localhost",  # Или IP-адрес
        port="5432"
    )

    # Проверяем на существование уже добавленных данных
    cur = conn.cursor()
    existing_keys = pd.read_sql("SELECT Ключ FROM tasks", conn)['Ключ'].tolist()
    merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]

    if not merged_df.empty:
        # Добавляем новые данные в таблицу tasks
        merged_df.to_sql('tasks', conn, if_exists='append', index=False)
        print(f"Добавлено новых строк: {len(merged_df)}")
    else:
        print("Новых уникальных данных нет.")

    # Закрытие соединения с базой данных
    conn.commit()
    cur.close()
    conn.close()

    # Перемещаем исходные файлы в архив
    for f_item in files[:2]:
        y.move(f_item.path, f"{archive_path}/{f_item.name}")

if __name__ == "__main__":
    process()
