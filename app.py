import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os

# Настройка страницы
st.set_page_config(page_title="Анализ дежурств", layout="wide")

# Авторизация и загрузка базы с Яндекса
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600) # Кэшируем данные на 10 минут
def load_data():
    if y.exists(DB_PATH):
        y.download(DB_PATH, "local_view.db")
        conn = sqlite3.connect("local_view.db")
        df = pd.read_sql("SELECT * FROM tasks", conn)
        conn.close()
        # Считаем TTM на лету
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].sum(axis=1) / 1440
        df['Дата создания'] = pd.to_datetime(df['Дата создания']).dt.date
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных пуста или не найдена на Яндекс Диске.")
else:
    st.title("Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ С ФИЛЬТРАМИ ---
    st.sidebar.header("Фильтры")
    
    # Фильтр по датам
    min_date = df['Дата создания'].min()
    max_date = df['Дата создания'].max()
    date_range = st.sidebar.date_input("Выберите период", [min_date, max_date])

    # Фильтр по командам
    all_teams = sorted(df['Компоненты'].unique().tolist())
    selected_teams = st.sidebar.multiselect("Выберите команды", all_teams, default=all_teams)

    # Применение фильтров
    mask = (df['Дата создания'] >= date_range[0]) & (df['Дата создания'] <= date_range[1]) & (df['Компоненты'].isin(selected_teams))
    filtered_df = df.loc[mask]

    # --- ГЛАВНЫЕ МЕТРИКИ (KPI) ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Всего задач", len(filtered_df))
    col2.metric("Средний TTM (дни)", round(filtered_df['ttm_days'].mean(), 2))
    col3.metric("Средний Пинг-понг", round(filtered_df['Пинг-понг обращения'].mean(), 1))

    # --- ГРАФИКИ ---
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Нагрузка по командам")
        fig_team = px.bar(filtered_df.groupby('Компоненты').size().reset_index(name='Задач'), 
                          x='Компоненты', y='Задач', color='Компоненты')
        st.plotly_chart(fig_team, use_container_width=True)

    with c2:
        st.subheader("Динамика поступления задач")
        fig_date = px.line(filtered_df.groupby('Дата создания').size().reset_index(name='Задач'), 
                           x='Дата создания', y='Задач')
        st.plotly_chart(fig_date, use_container_width=True)

    st.subheader("Распределение TTM по задачам")
    fig_ttm = px.histogram(filtered_df, x='ttm_days', nbins=20, labels={'ttm_days':'Дни'}, color_discrete_sequence=['indianred'])
    st.plotly_chart(fig_ttm, use_container_width=True)
