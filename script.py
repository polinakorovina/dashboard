import pandas as pd
import yadisk
import io
import os
from sqlalchemy import create_engine, text

# Авторизация и настройки
TOKEN = os.getenv("YANDEX_TOKEN")
# URL базы берем из GitHub Secrets (формат: postgresql://avnadmin:pass@host:port/defaultdb)
DB_URL = os.getenv("DB_URL") 

y = yadisk.YaDisk(token=TOKEN)

def process():
    input_path = "/Data/Input"
    archive_path = "/Data/Archive"
    
    # 1. Загружаем файлы с Яндекс.Диска
    try:
        items = list(y.listdir(input_path))
    except Exception:
        print("Папка не найдена.")
        return

    files = [item for item in items if item.type == 'file']
    if len(files) < 2:
        print("Нужно 2 файла для объединения.")
        return

    # 2. Читаем данные в память
    dfs = []
    for f_item in files[:2]:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            df = pd.read_csv(buf) if f_item.name.endswith('.csv') else pd.read_excel(buf)
            dfs.append(df)

    # 3. Объединение и очистка (ваша логика без изменений)
    df_left, df_right = dfs[0], dfs[1]
    # ... (логика объединения ключей как в вашем коде) ...
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else:
        print("Ключи не найдены."); return

    cols_to_drop = ['Статус', 'Дата завершения', 'DutyGPT prediction result', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    # Применяем вашу функцию очистки компонентов
    if 'Компоненты' in merged_df.columns:
        # (clean_components функция должна быть определена выше)
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # --- РАБОТА С POSTGRESQL (AIVEN) ---
    if not DB_URL:
        print("Ошибка: DB_URL не настроен."); return
    
    engine = create_engine(DB_URL)

    # 4. Проверка на дубликаты прямо в базе
    try:
        with engine.connect() as conn:
            # Получаем список уже существующих ключей из таблицы 'tasks'
            existing_keys = pd.read_sql("SELECT \"Ключ\" FROM tasks", conn)['Ключ'].tolist()
            merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]
    except Exception as e:
        print(f"Таблицы еще нет или ошибка чтения: {e}")

    # 5. Запись новых данных
    if not merged_df.empty:
        # Записываем в таблицу 'tasks'. SQLAlchemy сама создаст её, если её нет.
        merged_df.to_sql('tasks', engine, if_exists='append', index=False)
        print(f"В Aiven добавлено новых строк: {len(merged_df)}")
    else:
        print("Новых уникальных данных для базы нет.")

    # 6. Перемещаем файлы в архив на Диске
    for f_item in files[:2]:
        y.move(f_item.path, f"{archive_path}/{f_item.name}")

    print("Процесс полностью автоматизирован и завершен.")

if __name__ == "__main__":
    process()
