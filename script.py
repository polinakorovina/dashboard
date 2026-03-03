import pandas as pd
import yadisk
import io
import os
from sqlalchemy import create_engine

# --- 1. СНАЧАЛА ОПРЕДЕЛЯЕМ ВСЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_components(val):
    """Функция очистки компонентов (ваша логика)"""
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

# --- 2. ОСНОВНАЯ ЛОГИКА ---

def process():
    # Настройки из переменных окружения
    TOKEN = os.getenv("YANDEX_TOKEN")
    DB_URL = os.getenv("DB_URL") 
    
    y = yadisk.YaDisk(token=TOKEN)
    
    input_path = "/Data/Input"
    archive_path = "/Data/Archive"
    
    # Загружаем файлы с Яндекс.Диска
    try:
        items = list(y.listdir(input_path))
    except Exception as e:
        print(f"Ошибка доступа к диску: {e}")
        return

    files = [item for item in items if item.type == 'file']
    if len(files) < 2:
        print("Нужно минимум 2 файла для объединения.")
        return

    # Читаем данные
    dfs = []
    for f_item in files[:2]:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            if f_item.name.endswith('.csv'):
                df = pd.read_csv(buf)
            else:
                df = pd.read_excel(buf)
            dfs.append(df)

    # Объединение
    df_left, df_right = dfs[0], dfs[1]
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else:
        print("Ключи не найдены."); return

    # Очистка
    cols_to_drop = ['Статус', 'Дата завершения', 'DutyGPT prediction result', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    if 'Компоненты' in merged_df.columns:
        # Теперь clean_components определена выше и ошибки не будет
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # Запись в базу Aiven
    if not DB_URL:
        print("Ошибка: DB_URL не настроен."); return
    
    engine = create_engine(DB_URL)

    try:
        with engine.connect() as conn:
            # Проверяем на дубликаты
            existing_keys = pd.read_sql("SELECT \"Ключ\" FROM tasks", conn)['Ключ'].tolist()
            merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]
    except Exception:
        # Если таблицы нет, просто идем дальше (она создастся при to_sql)
        pass

    if not merged_df.empty:
        merged_df.to_sql('tasks', engine, if_exists='append', index=False)
        print(f"Добавлено строк в базу: {len(merged_df)}")
    else:
        print("Новых строк нет.")

    # Архивируем файлы
    for f_item in files[:2]:
        y.move(f_item.path, f"{archive_path}/{f_item.name}")

    print("Процесс завершен.")

if __name__ == "__main__":
    process()
