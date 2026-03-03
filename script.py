import pandas as pd
import yadisk
import io
import os
from sqlalchemy import create_engine

# --- 1. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

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

# --- 2. ОСНОВНАЯ ФУНКЦИЯ ---

def process():
    TOKEN = os.getenv("YANDEX_TOKEN")
    DB_URL = os.getenv("DB_URL")
    # Исправляем протокол, если он старого формата
    if DB_URL and DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
        
    y = yadisk.YaDisk(token=TOKEN)

    input_path = "/Data/Input"
    archive_path = "/Data/Archive"

    try:
        items = list(y.listdir(input_path))
    except Exception as e:
        print(f"Ошибка доступа к Диску: {e}")
        return

    files = [item for item in items if item.type == 'file' and item.name.endswith(('.csv', '.xlsx'))]
    if len(files) < 2:
        print("Нужно минимум 2 файла для работы.")
        return

    dfs = []
    processed_files = files[:2]
    
    for f_item in processed_files:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            df = pd.read_csv(buf) if f_item.name.endswith('.csv') else pd.read_excel(buf)
            dfs.append(df)

    df_left, df_right = dfs[0], dfs[1]
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else:
        print("Ключи для объединения не найдены.")
        return

    # --- ШАГ 3.1: ЗАПОЛНЕНИЕ ПРОПУСКОВ ---
    if 'Количество обращений' in merged_df.columns:
        merged_df['Количество обращений'] = merged_df['Количество обращений'].fillna('1-4')
    
    if 'Пинг-понг обращения' in merged_df.columns:
        merged_df['Пинг-понг обращения'] = merged_df['Пинг-понг обращения'].fillna(1.0)

    cols_to_drop = ['Статус', 'Дата завершения', 'DutyGPT prediction result', 
                    'Резолюция по ролям', 'Причина блокировки', 'Закрыт', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    if 'Резолюция' in merged_df.columns:
        merged_df = merged_df[~merged_df['Резолюция'].isin(['Не будет исправлено', 'Дубликат'])]

    if 'Компоненты' in merged_df.columns:
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # Шаг 4: Запись в базу
    if DB_URL:
        try:
            engine = create_engine(DB_URL)
            with engine.connect() as conn:
                # Проверяем на дубликаты перед вставкой
                try:
                    existing_keys = pd.read_sql('SELECT "Ключ" FROM tasks', conn)['Ключ'].tolist()
                    merged_df = merged_df[~merged_df['Ключ'].isin(existing_keys)]
                except:
                    pass 

                
                if not merged_df.empty:
                    merged_df.to_sql('tasks', engine, if_exists='append', index=False)
                    print(f"Добавлено в базу строк: {len(merged_df)}")
                else:
                    print("Новых строк для базы нет.")
                
        except Exception as e:
            print(f"ОШИБКА БАЗЫ ДАННЫХ: {e}")
    
    # Шаг 5: Перенос файлов
    for f_item in processed_files:
        dest_path = f"{archive_path}/{f_item.name}"
        try:
            if y.exists(dest_path):
                y.remove(dest_path)
            y.move(f_item.path, dest_path)
            print(f"Файл {f_item.name} перемещен в архив.")
        except Exception as e:
            print(f"Не удалось переместить {f_item.name}: {e}")

if __name__ == "__main__":
    process()
