import pandas as pd
import yadisk
import io
import os
import sqlite3

# Авторизация
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)

def process():
    input_path = "/Data/Input"
    archive_path = "/Data/Archive"
    db_file_path = "/Data/my_database.db"

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

    # --- ОБЪЕДИНЕНИЕ ---
    df_left, df_right = dfs[0], dfs[1]
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else: 
        print("Не найдены ключи объединения.")
        return

    # --- ОЧИСТКА ---
    cols_to_drop = ['Приоритет', 'Статус', 'Дата завершения', 'DutyGPT prediction result', 
                    'Резолюция по ролям', 'Причина блокировки', 'Закрыт', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    if 'Резолюция' in merged_df.columns:
        merged_df = merged_df[~merged_df['Резолюция'].isin(['Не будет исправлено', 'Дубликат'])]

    def clean_components(val):
        if pd.isna(val): return None
        comps = [c.strip() for c in str(val).split(',') if c.strip()]
        if len(comps) == 1 and comps[0] == "Запуск скрипта": return None
        if len(comps) >= 2:
            if "Запуск скрипта" in comps:
                comps.remove("Запуск скрипта")
                return comps[0] if len(comps) == 1 else None
            return None
        return val

    if 'Компоненты' in merged_df.columns:
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # --- РАБОТА С SQLITE ---
    local_db = "temp_db.db"
    if y.exists(db_file_path):
        y.download(db_file_path, local_db)
    
    conn = sqlite3.connect(local_db)
    
    # Если таблица уже есть, удаляем из новых данных то, что уже есть в базе
    try:
        existing_keys = pd.read_sql("SELECT Ключ FROM tasks", conn)['Ключ'].tolist()
        merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]
    except:
        # Если таблицы еще нет, это произойдет при первом запуске
        pass

    if not merged_df.empty:
        merged_df.to_sql('tasks', conn, if_exists='append', index=False)
        print(f"Добавлено новых строк: {len(merged_df)}")
    else:
        print("Новых уникальных данных нет.")
        
    conn.close()

    # Загружаем обратно
    with open(local_db, "rb") as f:
        if y.exists(db_file_path): y.remove(db_file_path)
        y.upload(f, db_file_path)

    # Перенос в архив
    for f_item in files[:2]:
        y.move(f_item.path, f"{archive_path}/{f_item.name}")
    
    if os.path.exists(local_db): os.remove(local_db)
    print("Процесс завершен.")

if __name__ == "__main__":
    process()
