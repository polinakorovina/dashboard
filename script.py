import pandas as pd
import yadisk
import io
import os
from sqlalchemy import create_engine

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

def process():
    TOKEN = os.getenv("YANDEX_TOKEN")
    DB_URL = os.getenv("DB_URL")
    
    # 1. Быстрое исправление протокола
    if DB_URL and DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
        
    y = yadisk.YaDisk(token=TOKEN)
    input_path = "/Data/Input"
    archive_path = "/Data/Archive"

    # 2. Быстрое получение списка файлов
    try:
        items = list(y.listdir(input_path))
    except Exception as e:
        print(f"Ошибка доступа к Диску: {e}")
        return

    files = [item for item in items if item.type == 'file' and item.name.endswith(('.csv', '.xlsx'))]
    if len(files) < 2:
        print("Нужно минимум 2 файла для работы.")
        return

    # Обрабатываем только первые два найденных файла
    dfs = []
    processed_files = files[:2]
    
    for f_item in processed_files:
        with io.BytesIO() as buf:
            y.download(f_item.path, buf)
            buf.seek(0)
            # Быстрое чтение
            df = pd.read_csv(buf) if f_item.name.endswith('.csv') else pd.read_excel(buf)
            dfs.append(df)

    df_left, df_right = dfs[0], dfs[1]
    
    # 3. Объединение данных
    if 'Ключ' in df_left.columns and 'issue_key' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='Ключ', right_on='issue_key', how='left')
    elif 'issue_key' in df_left.columns and 'Ключ' in df_right.columns:
        merged_df = pd.merge(df_left, df_right, left_on='issue_key', right_on='Ключ', how='left')
    else:
        print("Ключи для объединения не найдены.")
        return

    # 4. Быстрое заполнение пропусков (Векторизовано)
    if 'Количество обращений' in merged_df.columns:
        merged_df['Количество обращений'] = merged_df['Количество обращений'].fillna('1-4')
    
    if 'Пинг-понг обращений' in merged_df.columns:
        merged_df['Пинг-понг обращений'] = merged_df['Пинг-понг обращений'].fillna(1.0)

    # Очистка колонок
    cols_to_drop = ['Статус', 'Дата завершения', 'DutyGPT prediction result', 
                    'Резолюция по ролям', 'Причина блокировки', 'Закрыт', 'issue_key']
    merged_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    # Фильтрация
    if 'Резолюция' in merged_df.columns:
        merged_df = merged_df[~merged_df['Резолюция'].isin(['Не будет исправлено', 'Дубликат'])]

    if 'Компоненты' in merged_df.columns:
        merged_df['Компоненты'] = merged_df['Компоненты'].apply(clean_components)
        merged_df.dropna(subset=['Компоненты'], inplace=True)

    # 5. СВЕРХБЫСТРАЯ ЗАПИСЬ В БАЗУ
    if DB_URL:
        try:
            # pool_recycle помогает избежать разрыва соединения
            engine = create_engine(DB_URL, pool_recycle=3600)
            
            if not merged_df.empty:
                # method='multi' ускоряет процесс в десятки раз
                # chunksize=1000 отправляет данные пачками по 1000 строк
                merged_df.to_sql(
                    'tasks', 
                    engine, 
                    if_exists='replace', 
                    index=False, 
                    method='multi', 
                    chunksize=1000
                )
                print(f"База обновлена успешно. Записано строк: {len(merged_df)}")
            else:
                print("Нет данных для записи.")
        except Exception as e:
            print(f"ОШИБКА БАЗЫ ДАННЫХ: {e}")
    
    # 6. Быстрое перемещение файлов
    for f_item in processed_files:
        dest_path = f"{archive_path}/{f_item.name}"
        try:
            if y.exists(dest_path):
                y.remove(dest_path)
            y.move(f_item.path, dest_path)
            print(f"Файл {f_item.name} в архиве.")
        except Exception as e:
            print(f"Ошибка перемещения {f_item.name}: {e}")

if __name__ == "__main__":
    process()
