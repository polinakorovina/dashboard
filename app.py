import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import datetime, timedelta

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- BI-ОФОРМЛЕНИЕ (Shadow Cards + Clean UI) ---
st.markdown(f"""
    <style>
    /* Общий фон страницы (светло-серый, как в BI) */
    .stApp {{
        background-color: #F4F7F9;
    }}
    
    /* Сайдбар */
    [data-testid="stSidebar"] {{
        background-color: #A485E0;
    }}
    [data-testid="stSidebar"] {{
        color: white;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p {{
        color: white !important;
    }}

    /* Стилизация метрик (Белые карточки) */
    div[data-testid="metric-container"] {{
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        border: 1px solid #E6E9EF;
    }}
    
    div[data-testid="stMetricValue"] {{
        color: #6244BB !important;
        font-weight: 700 !important;
    }}

    /* Контейнеры для графиков (Shadow Cards) */
    .bi-card {{
        background-color: white;
        padding: 24px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        border: 1px solid #E6E9EF;
        margin-bottom: 25px;
    }}

    /* Красивые заголовки */
    .main-title {{
        font-size: 32px;
        font-weight: 800;
        color: #1A1C1E;
        margin-bottom: 25px;
        display: flex;
        align-items: center;
    }}
    
    .card-title {{
        font-size: 18px;
        font-weight: 700;
        color: #1A1C1E;
        margin-bottom: 15px;
    }}

    /* Мультиселект и кнопки */
    .stMultiSelect span {{
        background-color: #6244BB !important;
    }}
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
        
        for col in ['Приоритет', 'Кол-во обращений', 'Компоненты', 'Резолюция']:
            if col not in df.columns: df[col] = 'Unknown' if col != 'Кол-во обращений' else 0
            
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        df['Резолюция'] = df['Резолюция'].fillna('Не указано')
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных пуста.")
else:
    # --- САЙДБАР (ВОЗВРАЩЕНЫ ВСЕ ФИЛЬТРЫ) ---
    st.sidebar.header("Настройки фильтров")
    
    db_min, db_max = df['Дата создания'].min().date(), df['Дата создания'].max().date()
    start_last_week = db_max - timedelta(days=db_max.weekday())
    
    date_range = st.sidebar.date_input("Период анализа", value=(start_last_week, db_max), min_value=db_min, max_value=db_max)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        st.sidebar.markdown("---")
        all_teams = sorted(df['Компоненты'].unique().tolist())
        select_all_teams = st.sidebar.checkbox("Выбрать все команды", value=True)
        sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams if select_all_teams else [])

        all_res = sorted(df['Резолюция'].unique().tolist())
        select_all_res = st.sidebar.checkbox("Выбрать все резолюции", value=True)
        sel_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res if select_all_res else [])

        # Фильтрация
        f_df = df[(df['Дата создания'] >= start_date) & (df['Дата создания'] <= end_date) & 
                  (df['Компоненты'].isin(sel_teams)) & (df['Резолюция'].isin(sel_res))].copy()

        # --- ЗАГОЛОВОК ---
        st.markdown('<div class="main-title">📊 Аналитика дежурств</div>', unsafe_allow_html=True)

        # --- KPI ---
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1: st.metric("TTM (средний)", f"{f_df['ttm_days'].mean() if not f_df.empty else 0:.2f}")
        with kpi2: st.metric("Критичные 'Позже'", len(f_df[(f_df['Резолюция'] == 'Позже') & (f_df['Приоритет'] == 'Критичный')]))
        with kpi3: st.metric("Всего задач", len(f_df))

        st.markdown("<br>", unsafe_allow_html=True)

        # --- ГРАФИКИ: НАГРУЗКА И ВРЕМЯ (КАК НА СКРИНЕ) ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Нагрузка по командам</div>', unsafe_allow_html=True)
            if not f_df.empty:
                t_counts = f_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во')
                t_order = f_df['Компоненты'].value_counts().index.tolist()
                fig_l = px.bar(t_counts, x='Кол-во', y='Компоненты', color='Резолюция', orientation='h', 
                               text='Кол-во', category_orders={"Компоненты": t_order},
                               color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
                fig_l.update_traces(textposition='outside')
                fig_l.update_layout(height=450, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=10, b=0))
                st.plotly_chart(fig_l, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Среднее время работы</div>', unsafe_allow_html=True)
            if not f_df.empty:
                t_avg = f_df.groupby('Компоненты')['ttm_days'].mean().reset_index()
                t_avg['Компоненты'] = pd.Categorical(t_avg['Компоненты'], categories=t_order, ordered=True)
                t_avg = t_avg.sort_values('Компоненты', ascending=False)
                fig_a = px.bar(t_avg, x='ttm_days', y='Компоненты', orientation='h', text_auto='.1f',
                               color_discrete_sequence=['#6244BB'], template="plotly_white")
                fig_a.update_traces(textposition='outside')
                fig_a.update_layout(height=450, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=10, b=0))
                st.plotly_chart(fig_a, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- ДИНАМИКА (С ВЫБОРОМ ВНУТРИ) ---
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        dh1, dh2 = st.columns([4, 1])
        with dh1: st.markdown('<div class="card-title">📈 Динамика поступления</div>', unsafe_allow_html=True)
        with dh2: unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")
        
        if not f_df.empty:
            u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
            resampled = f_df.set_index('Дата создания').resample(u_map[unit]).size().reset_index(name='Задач')
            fig_d = px.line(resampled, x='Дата создания', y='Задач', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
            fig_d.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), xaxis_title=None)
            st.plotly_chart(fig_d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- НИЖНИЙ РЯД: TTM И МАССОВЫЕ ---
        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Распределение TTM (Гистограмма)</div>', unsafe_allow_html=True)
            fig_h = px.histogram(f_df, x='ttm_days', nbins=20, color_discrete_sequence=['#6244BB'], template="plotly_white", marginal="violin")
            st.plotly_chart(fig_h, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c4:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Массовые обращения (11+)</div>', unsafe_allow_html=True)
            mass = f_df[f_df['Кол-во обращений'] >= 11]
            if not mass.empty:
                m_ch = mass.groupby('Кол-во обращений')['ttm_days'].mean().reset_index()
                fig_m = px.line(m_ch, x='Кол-во обращений', y='ttm_days', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
                st.plotly_chart(fig_m, use_container_width=True)
            else: st.write("Нет данных")
            st.markdown('</div>', unsafe_allow_html=True)

        # --- ПРОЦЕНТ ОЖИДАНИЯ ---
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Процент времени до начала работы</div>', unsafe_allow_html=True)
        pre_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки']
        avail = [c for c in pre_cols if c in f_df.columns]
        f_df['pre_min'] = f_df[avail].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
        f_df['pct_wait'] = f_df.apply(lambda x: (x['pre_min'] / (x['ttm_days'] * 1440) * 100) if x['ttm_days'] > 0 else 0, axis=1)
        fig_p = px.histogram(f_df, x='pct_wait', nbins=20, color_discrete_sequence=['#A485E0'], template="plotly_white")
        st.plotly_chart(fig_p, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
