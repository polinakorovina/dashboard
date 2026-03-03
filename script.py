import pandas as pd
import yadisk
import io
import os
from sqlalchemy import create_engine

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_components(val):
    if pd.isna(val):
        return None
    comps = [c.strip() for c in str(val).split(',') if c.strip()]
    if len(comps) == 1 and comps[0] == "Запуск скрипта":
        return None
    if len(comps) >= 2:
        if "Запуск скрипта" in comps:
            comps.remove("Запуск скрипта")
            return comps[0] if len(comps) == 1 else None
        return None
    return val

# --- ОСНОВНАЯ ФУНКЦИЯ ---

def process():
    TOKEN = os.getenv("YANDEX_TOKEN")
    DB_URL = os.getenv("DB_URL")
    y = yadisk.YaDisk(token=TOKEN)

    input_path = "/Data/Input"
    archive_path = "/Data/Archive"

    # 1. Получаем список файлов
    try:
        items = list(y.listdir(input_path))
    except Exception as e:
        print(f"Ошибка: Папка не найдена или нет доступа. {e}")
        return

    files = [item for item in items if item.type == 'file']
    if len(files) < 2:
        print("Нужно минимум 2 файла для работы.")
        return

    # 2. Загружаем данные (берем первые 2 файла)
    dfs = []
    processed_files = files[:2] # Запоминаем, какие именно файлы мы взяли
    
    for f_item in processed_files:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            df = pd.read_csv(buf) if f_item.name.endswith('.csv') else pd.read_excel(buf)
            dfs.append(df)

    # 3. Объединение (Твоя логика)
    df_left, df_right = dfs[0], dfs[1]
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else:
        print("Не найдены ключи для объединения."); return

    # 4. Очистка
    cols_to_drop = ['Статус', 'Дата завершения', 'DutyGPT prediction result', 
                    'Резолюция по ролям', 'Причина блокировки', 'Закрыт', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    if 'Резолюция' in merged_df.columns:
        merged_df = merged_df[~merged_df['Резолюция'].isin(['Не будет исправлено', 'Дубликат'])]

    if 'Компоненты' in merged_df.columns:
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # 5. Запись в Aiven PostgreSQL
    if not DB_URL:
        print("Ошибка: Переменная DB_URL не настроена."); return
    
    engine = create_engine(DB_URL)

    try:
        with engine.connect() as conn:
            # Проверка на дубликаты
            existing_keys = pd.read_sql('SELECT "Ключ" FROM tasks', conn)['Ключ'].tolist()
            merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]
    except Exception:
        pass # Если таблицы нет, она создастся ниже

    if not merged_df.empty:
        merged_df.to_sql('tasks', engine, if_exists='append', index=False)
        print(f"Добавлено новых строк в базу: {len(merged_df)}")
    else:
        print("Новых уникальных данных нет.")

    # 6. ПЕРЕНОС ФАЙЛОВ (Твоя оригинальная логика)
    # Мы используем список processed_files, который определили в начале
    # Перемещаем исходные файлы в архив
    for f_item in files[:2]:
        y.move(f_item.path, f"{archive_path}/{f_item.name}")

    print("Процесс завершен.")

if __name__ == "__main__":
    process()
