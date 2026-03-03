import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import datetime, timedelta

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- BI-СТИЛЬ (Оформление карточек и ячеек) ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #F8F9FB; }}
    [data-testid="stSidebar"] {{ background-color: #A485E0; color: white; }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{
        color: white !important;
    }}
    div[data-testid="metric-container"] {{
        background-color: white;
        padding: 20px 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #E6E9EF;
        text-align: center;
    }}
    div[data-testid="stMetricValue"] {{ color: #6244BB !important; font-weight: 800 !important; font-size: 2.5rem !important; }}
    .bi-card {{
        background-color: white;
        padding: 24px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
        border: 1px solid #E6E9EF;
        margin-bottom: 24px;
    }}
    .main-header {{ font-size: 34px; font-weight: 800; color: #1A1C1E; margin-bottom: 30px; }}
    .card-header {{ font-size: 18px; font-weight: 700; color: #1A1C1E; margin-bottom: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# 2. Загрузка данных
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
        
        # Список колонок для расчетов
        ttm_stages = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        cycle_stages = ['Бэклог разработки', 'В работе']
        
        # Проверка наличия колонок и замена NaN на 0
        for col in ttm_stages:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        # Расчет по твоим формулам (сумма минут / 1440 = дни)
        df['ttm_days'] = df[ttm_stages].sum(axis=1) / 1440
        df['cycle_time'] = df[cycle_stages].sum(axis=1) / 1440
        
        df['Резолюция'] = df['Резолюция'].fillna('Не указано')
        return df
    return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- САЙДБАР ---
    st.sidebar.header("Настройки фильтров")
    db_min, db_max = df['Дата создания'].min().date(), df['Дата создания'].max().date()
    date_range = st.sidebar.date_input("Период анализа", value=(db_max - timedelta(days=7), db_max), min_value=db_min, max_value=db_max)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        
        # Фильтры по командам и резолюциям
        all_teams = sorted(df['Компоненты'].unique().tolist())
        sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams)
        all_res = sorted(df['Резолюция'].unique().tolist())
        sel_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res)

        f_df = df[(df['Дата создания'] >= start_d) & (df['Дата создания'] <= end_d) & 
                  (df['Компоненты'].isin(sel_teams)) & (df['Резолюция'].isin(sel_res))].copy()

        # --- ЗАГОЛОВОК И KPI ---
        st.markdown('<div class="main-header">📊 Аналитика дежурств</div>', unsafe_allow_html=True)
        
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric("TTM (средний)", f"{f_df['ttm_days'].mean():.2f}")
        with k2: st.metric("Cycle Time", f"{f_df['cycle_time'].mean():.2f}")
        with k3: 
            crit = len(f_df[(f_df['Резолюция'] == 'Позже') & (f_df.get('Приоритет','') == 'Критичный')])
            st.metric("Критичные 'Позже'", crit)
        with k4: st.metric("Всего задач", len(f_df))

        st.markdown("<br>", unsafe_allow_html=True)

        # --- ГРАФИКИ (Нагрузка и Время) ---
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-header">Нагрузка по командам</div>', unsafe_allow_html=True)
            t_counts = f_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во')
            t_order = f_df['Компоненты'].value_counts().index.tolist()
            fig_l = px.bar(t_counts, x='Кол-во', y='Компоненты', color='Резолюция', orientation='h', 
                           text='Кол-во', category_orders={"Компоненты": t_order},
                           color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
            fig_l.update_traces(textposition='outside')
            fig_l.update_layout(height=400, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=0, b=0))
            st.plotly_chart(fig_l, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-header">Среднее время работы (TTM)</div>', unsafe_allow_html=True)
            t_avg = f_df.groupby('Компоненты')['ttm_days'].mean().reset_index()
            t_avg['Компоненты'] = pd.Categorical(t_avg['Компоненты'], categories=t_order, ordered=True)
            t_avg = t_avg.sort_values('Компоненты', ascending=False)
            fig_a = px.bar(t_avg, x='ttm_days', y='Компоненты', orientation='h', text_auto='.1f',
                           color_discrete_sequence=['#6244BB'], template="plotly_white")
            fig_a.update_traces(textposition='outside')
            fig_a.update_layout(height=400, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=0, b=0))
            st.plotly_chart(fig_a, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- ДИНАМИКА ---
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        dh1, dh2 = st.columns([5, 1])
        with dh1: st.markdown('<div class="card-header">📈 Динамика поступления</div>', unsafe_allow_html=True)
        with dh2: unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")
        
        u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
        resampled = f_df.set_index('Дата создания').resample(u_map[unit]).size().reset_index(name='Задач')
        fig_d = px.line(resampled, x='Дата создания', y='Задач', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
        fig_d.update_layout(height=300, xaxis_title=None)
        st.plotly_chart(fig_d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
