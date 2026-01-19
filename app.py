import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2. Авторизация и загрузка базы с Яндекса
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600)
def load_data():
    if y.exists(DB_PATH):
        # Скачиваем базу во временный файл
        y.download(DB_PATH, "local_view.db")
        conn = sqlite3.connect("local_view.db")
        df = pd.read_sql("SELECT * FROM tasks", conn)
        conn.close()
        
        # Безопасное преобразование даты
        df['Дата создания'] = pd.to_datetime(df['Дата создания'], errors='coerce')
        df = df.dropna(subset=['Дата создания'])
        df['Дата создания'] = df['Дата создания'].dt.date
        
        # Считаем TTM на лету (из минут в дни)
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        # Превращаем в числа и суммируем
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        # Заполняем пустой пинг-понг единицей
        if 'Пинг-понг обращения' in df.columns:
            df['Пинг-понг обращения'] = pd.to_numeric(df['Пинг-понг обращения'], errors='coerce').fillna(1)
            
        return df
    return pd.DataFrame()

# Загружаем данные
df = load_data()

# 3. Проверка на наличие данных
if df.empty:
    st.error("База данных пуста или не найдена на Яндекс Диске по пути /Data/my_database.db")
    st.info("Проверьте, что ваш основной скрипт успешно отработал и создал файл.")
else:
    st.title("📊 Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ С ФИЛЬТРАМИ ---
    st.sidebar.header("Настройки фильтров")
    
    # Определяем границы существующих дат
    min_d = df['Дата создания'].min()
    max_d = df['Дата создания'].max()

    # Виджет выбора диапазона дат
    date_range = st.sidebar.date_input(
        "Выберите период анализа",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d
    )

    # Логика фильтрации (работает только когда выбраны две даты)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        
        # Фильтр по командам
        all_teams = sorted(df['Компоненты'].unique().tolist())
        selected_teams = st.sidebar.multiselect("Выберите команды (компоненты)", all_teams, default=all_teams)

        # Применяем фильтрацию к данным
        mask = (df['Дата создания'] >= start_date) & \
               (df['Дата создания'] <= end_date) & \
               (df['Компоненты'].isin(selected_teams))
        filtered_df = df.loc[mask]

        # --- ОСНОВНЫЕ МЕТРИКИ (KPI) ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего задач", len(filtered_df))
        with col2:
            avg_ttm = filtered_df['ttm_days'].mean()
            st.metric("Средний TTM (дни)", f"{avg_ttm:.2f}")
        with col3:
            avg_ping = filtered_df['Пинг-понг обращения'].mean()
            st.metric("Средний Пинг-понг", f"{avg_ping:.1f}")

        st.markdown("---")

        # --- ГРАФИКИ ---
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Нагрузка по командам")
            team_counts = filtered_df.groupby('Компоненты').size().reset_index(name='Кол-во задач')
            fig_team = px.bar(team_counts, x='Компоненты', y='Кол-во задач', 
                              color='Компоненты', template="seaborn")
            st.plotly_chart(fig_team, use_container_width=True)

        with c2:
            st.subheader("Динамика поступления")
            date_counts = filtered_df.groupby('Дата создания').size().reset_index(name='Кол-во задач')
            fig_date = px.line(date_counts, x='Дата создания', y='Кол-во задач', 
                               markers=True, template="seaborn")
            st.plotly_chart(fig_date, use_container_width=True)

        st.subheader("Распределение скорости решения (TTM)")
        fig_ttm = px.histogram(filtered_df, x='ttm_days', nbins=30, 
                               labels={'ttm_days':'Дни на решение'},
                               color_discrete_sequence=['#636EFA'],
                               marginal="box") # Добавляем "ящик с усами" сверху для наглядности
        st.plotly_chart(fig_ttm, use_container_width=True)

        # --- ТАБЛИЦА САМЫХ ДОЛГИХ ЗАДАЧ ---
        st.subheader("🚩 Топ-5 задач с самым долгим решением")
        top_slow = filtered_df.sort_values('ttm_days', ascending=False).head(5)
        if not top_slow.empty:
            st.table(top_slow[['Ключ', 'Компоненты', 'Дата создания', 'ttm_days']])

    else:
        # Если пользователь нажал на календарь, но не выбрал вторую дату
        st.info("💡 Пожалуйста, выберите в календаре дату начала и дату окончания периода.")

    # Кнопка для ручного обновления кэша
    if st.sidebar.button('🔄 Обновить данные с Я.Диска'):
        st.cache_data.clear()
        st.rerun()
