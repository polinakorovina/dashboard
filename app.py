import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import datetime, timedelta

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- СТИЛЬ "BI-ИНСТРУМЕНТ" ---
st.markdown(f"""
    <style>
    /* Фон всей страницы */
    .stApp {{
        background-color: #f8f9fa;
    }}
    
    /* Боковая панель */
    [data-testid="stSidebar"] {{
        background-color: #A485E0;
    }}
    [data-testid="stSidebar"] {{
        color: white;
    }}

    /* Стилизация карточек KPI */
    div[data-testid="metric-container"] {{
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #eee;
        text-align: center;
    }}
    
    /* Цвет заголовков KPI */
    div[data-testid="metric-container"] label {{
        color: #333 !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }}
    
    /* Цвет значений KPI */
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
        color: #6244BB !important;
        font-weight: 700 !important;
    }}

    /* Контейнеры для графиков */
    .plot-container {{
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
        margin-bottom: 20px;
        border: 1px solid #efefef;
    }}

    /* Заголовки */
    h1, h2, h3 {{
        color: #2D3436;
        font-family: 'Inter', sans-serif;
    }}
    
    /* Стили для Selectbox и других элементов */
    .stSelectbox label, .stMultiSelect label {{
        color: #333 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# 2. Авторизация и загрузка данных
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
        
        # Моковые или реальные расчеты (cycle time и т.д.)
        for col in ['Приоритет', 'Кол-во обращений']:
            if col not in df.columns: df[col] = 0
            
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        return df
    return pd.DataFrame()

df = load_data()

if not df.empty:
    # Фильтры в сайдбаре
    st.sidebar.header("Фильтры")
    # ... (стандартный блок фильтров)
    last_date = df['Дата создания'].max().date()
    date_range = st.sidebar.date_input("Период", value=(last_date - timedelta(days=7), last_date))
    
    # Фильтрация
    if isinstance(date_range, tuple) and len(date_range) == 2:
        f_df = df[(df['Дата создания'].dt.date >= date_range[0]) & (df['Дата создания'].dt.date <= date_range[1])]
    else:
        f_df = df

    st.title("📊 Аналитика дежурств")

    # --- KPI БЛОК (как в BI) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("TTM (средний)", f"{f_df['ttm_days'].mean():.2f}")
    with col2:
        # Пример cycle time (если есть в данных)
        st.metric("Cycle Time", f"{(f_df['ttm_days'].mean() * 0.3):.2f}") 
    with col3:
        st.metric("Всего задач", f"{len(f_df):,}".replace(",", " "))

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ГРАФИКИ В КАРТОЧКАХ ---
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.subheader("Нагрузка по командам")
        team_counts = f_df.groupby('Компоненты').size().sort_values(ascending=True).reset_index(name='Кол-во')
        fig_load = px.bar(team_counts, x='Кол-во', y='Компоненты', orientation='h',
                          color_discrete_sequence=['#6244BB'], template="plotly_white")
        fig_load.update_layout(margin=dict(l=20, r=20, t=5, b=20), height=400)
        st.plotly_chart(fig_load, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="plot-container">', unsafe_allow_html=True)
        st.subheader("Среднее время по командам")
        team_avg = f_df.groupby('Компоненты')['ttm_days'].mean().sort_values(ascending=True).reset_index()
        fig_avg = px.bar(team_avg, x='ttm_days', y='Компоненты', orientation='h',
                         color_discrete_sequence=['#A485E0'], template="plotly_white")
        fig_avg.update_layout(margin=dict(l=20, r=20, t=5, b=20), height=400)
        st.plotly_chart(fig_avg, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ЛИНЕЙНЫЙ ГРАФИК ---
    st.markdown('<div class="plot-container">', unsafe_allow_html=True)
    col_h, col_t = st.columns([3, 1])
    with col_h: st.subheader("Динамика поступления")
    with col_t:
        unit = st.selectbox("Группировка", ["День", "Неделя"], label_visibility="collapsed")
    
    u_map = {"День": "D", "Неделя": "W"}
    resampled = f_df.set_index('Дата создания').resample(u_map[unit]).size().reset_index(name='Задач')
    fig_line = px.line(resampled, x='Дата создания', y='Задач', markers=True,
                       color_discrete_sequence=['#6244BB'], template="plotly_white")
    fig_line.update_layout(margin=dict(l=20, r=20, t=10, b=20))
    st.plotly_chart(fig_line, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.error("Данные отсутствуют")
