import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import datetime, timedelta

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- ИНДИВИДУАЛЬНЫЙ СТИЛЬ (Фиолетовая тема) ---
st.markdown(f"""
    <style>
    /* 1. Цвет фона боковой панели и текста в ней */
    [data-testid="stSidebar"] {{
        background-color: #A485E0;
    }}
    [data-testid="stSidebar"] {{
        color: white;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stMarkdown {{
        color: white;
    }}

    /* 2. Радиокнопки и Чекбоксы */
    div[role="radiogroup"] div[data-baseweb="radio"] div:first-child {{
        border-color: #6244BB !important;
    }}
    div[role="radiogroup"] div[data-baseweb="radio"] div:first-child div:nth-child(2) {{
        background-color: #6244BB !important;
    }}
    div[data-testid="stCheckbox"] input[type="checkbox"]:checked + div {{
        background-color: #6244BB !important;
        border-color: #6244BB !important;
    }}
    div[data-testid="stCheckbox"] svg {{
        fill: white !important;
    }}

    /* 3. Мультиселект (Теги) */
    span[data-baseweb="tag"] {{
        background-color: #6244BB !important;
    }}
    
    /* 4. Календарь и общие акценты */
    :root {{
        --primary-color: #6244BB;
    }}
    </style>
    """, unsafe_allow_html=True)

# 2. Авторизация и загрузка базы с Яндекса
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600)
def load_data():
    if y.exists(DB_PATH):
        y.download(DB_PATH, "local_view.db")
        conn = sqlite3.connect("local_view.db")
        df = pd.read_sql("SELECT * FROM tasks", conn)
        conn.close()
        
        df['Дата создания'] = pd.to_datetime(df['Дата создания'], errors='coerce')
        df = df.dropna(subset=['Дата создания'])
        
        if 'Приоритет' not in df.columns: df['Приоритет'] = 'Не указан'
        if 'Кол-во обращений' not in df.columns: df['Кол-во обращений'] = 0
        if 'Ключ' not in df.columns: df['Ключ'] = 'Unknown'
            
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        df['Резолюция'] = df['Резолюция'].fillna('Не указано')
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных не найдена или пуста.")
else:
    last_date_in_db = df['Дата создания'].max().date()
    start_of_last_week = last_date_in_db - timedelta(days=last_date_in_db.weekday())
    db_min_date = df['Дата создания'].min().date()
    db_max_date = last_date_in_db

    st.title("💜 Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ ---
    st.sidebar.header("Настройки фильтров")
    date_range = st.sidebar.date_input(
        "Период анализа", 
        value=(start_of_last_week, db_max_date), 
        min_value=db_min_date, max_value=db_max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        # Выбор команд и резолюций
        st.sidebar.markdown("---")
        all_teams = sorted(df['Компоненты'].unique().tolist())
        select_all_teams = st.sidebar.checkbox("Выбрать все команды", value=True)
        selected_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams if select_all_teams else [])

        all_res = sorted(df['Резолюция'].unique().tolist())
        select_all_res = st.sidebar.checkbox("Выбрать все резолюции", value=True)
        selected_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res if select_all_res else [])

        mask = (df['Дата создания'] >= start_date) & (df['Дата создания'] <= end_date) & \
               (df['Компоненты'].isin(selected_teams)) & (df['Резолюция'].isin(selected_res))
        f_df = df.loc[mask].copy()

        # KPI
        priority_mask = (f_df['Резолюция'] == 'Позже') & (f_df['Приоритет'] == 'Критичный')
        total_priority_later = len(f_df[priority_mask])

        col1, col2, col3 = st.columns(3)
        col1.metric("Всего задач", len(f_df))
        col2.metric("Средний TTM (дни)", f"{f_df['ttm_days'].mean() if not f_df.empty else 0:.2f}")
        col3.metric("Критичные + 'Позже'", total_priority_later)

        st.markdown("---")

        # --- ГРАФИКИ В КОЛОНКАХ ---
        if not f_df.empty:
            team_counts = f_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во')
            total_order = f_df['Компоненты'].value_counts().index.tolist()
            
            team_avg_time = f_df.groupby('Компоненты')['ttm_days'].mean().reset_index()
            team_avg_time['Компоненты'] = pd.Categorical(team_avg_time['Компоненты'], categories=total_order, ordered=True)
            team_avg_time = team_avg_time.sort_values('Компоненты', ascending=False)
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Нагрузка по командам")
                fig_load = px.bar(
                    team_counts, x='Кол-во', y='Компоненты', color='Резолюция',
                    orientation='h', text='Кол-во',
                    category_orders={"Компоненты": total_order},
                    color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"},
                    template="plotly_white"
                )
                fig_load.update_traces(textposition='outside')
                fig_load.update_layout(xaxis_title="Количество задач", yaxis_title=None, margin=dict(r=50))
                st.plotly_chart(fig_load, use_container_width=True)

            with c2:
                st.subheader("Среднее время работы")
                fig_avg = px.bar(
                    team_avg_time, x='ttm_days', y='Компоненты',
                    orientation='h', text_auto='.1f',
                    color_discrete_sequence=['#6244BB'],
                    template="plotly_white"
                )
                fig_avg.update_traces(textposition='outside')
                fig_avg.update_layout(xaxis_title="Среднее время (дни)", yaxis_title=None, margin=dict(r=50))
                st.plotly_chart(fig_avg, use_container_width=True)
        
        st.markdown("---")

        # --- ДИНАМИКА ПОСТУПЛЕНИЯ ---
        col_h, col_t = st.columns([3, 1])
        with col_h: st.subheader("📈 Динамика поступления")
        with col_t:
            time_unit_local = st.selectbox("Группировка:", options=['День', 'Неделя', 'Месяц', 'Год'], index=0, key="loc_grp")
        
        if not f_df.empty:
            u_map = {'День': 'D', 'Неделя': 'W', 'Месяц': 'ME', 'Год': 'YE'}
            resampled = f_df.set_index('Дата создания').resample(u_map[time_unit_local]).size().reset_index(name='Задач')
            fig_date = px.line(resampled, x='Дата создания', y='Задач', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
            fig_date.update_layout(xaxis_title=None, yaxis_title="Количество задач")
            st.plotly_chart(fig_date, use_container_width=True)

        # --- TTM ---
        st.subheader("Распределение скорости решения (TTM)")
        if not f_df.empty:
            fig_ttm = px.histogram(f_df, x='ttm_days', nbins=20, color_discrete_sequence=['#6244BB'], template="plotly_white", marginal="violin")
            st.plotly_chart(fig_ttm, use_container_width=True)

        st.markdown("---")

        # --- МАССОВЫЕ ОБРАЩЕНИЯ И ПРОЦЕНТ ОЖИДАНИЯ ---
        cb1, cb2 = st.columns(2)
        with cb1:
            st.subheader("Массовые обращения (11+)")
            mass_df = f_df[f_df['Кол-во обращений'] >= 11]
            if not mass_df.empty:
                mass_chart = mass_df.groupby('Кол-во обращений')['ttm_days'].mean().reset_index()
                mass_chart['Кол-во_str'] = mass_chart['Кол-во обращений'].astype(int).astype(str) + "+"
                fig_mass = px.line(mass_chart, x='Кол-во_str', y='ttm_days', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
                st.plotly_chart(fig_mass, use_container_width=True)
            else: st.write("Нет массовых обращений")

        with cb2:
            st.subheader("Процент времени до работы")
            if not f_df.empty:
                pre_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки']
                avail = [c for c in pre_cols if c in f_df.columns]
                f_df['pre_min'] = f_df[avail].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
                f_df['pct_wait'] = f_df.apply(lambda x: (x['pre_min'] / (x['ttm_days'] * 1440) * 100) if x['ttm_days'] > 0 else 0, axis=1)
                fig_pct = px.histogram(f_df, x='pct_wait', nbins=20, color_discrete_sequence=['#A485E0'], template="plotly_white")
                st.plotly_chart(fig_pct, use_container_width=True)
    else:
        st.info("Выберите диапазон дат в левом меню.")
