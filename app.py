import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import datetime, timedelta

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- СТРОГИЙ BI-СТИЛЬ (Карточки, тени, ячейки) ---
st.markdown(f"""
    <style>
    /* Фон всей страницы */
    .stApp {{
        background-color: #F8F9FB;
    }}
    
    /* Боковая панель */
    [data-testid="stSidebar"] {{
        background-color: #A485E0;
    }}
    [data-testid="stSidebar"] {{
        color: white;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{
        color: white !important;
    }}

    /* Стилизация ячеек для цифр (KPI Cards) */
    div[data-testid="metric-container"] {{
        background-color: white;
        padding: 20px 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #E6E9EF;
        text-align: center;
    }}
    
    div[data-testid="stMetricValue"] {{
        color: #6244BB !important;
        font-weight: 800 !important;
        font-size: 2.5rem !important;
    }}
    
    div[data-testid="stMetricLabel"] p {{
        font-size: 1.1rem !important;
        color: #4F5E71 !important;
        font-weight: 600 !important;
    }}

    /* Контейнеры для графиков */
    .bi-card {{
        background-color: white;
        padding: 24px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
        border: 1px solid #E6E9EF;
        margin-bottom: 24px;
    }}

    /* Заголовки */
    .main-header {{
        font-size: 34px;
        font-weight: 800;
        color: #1A1C1E;
        margin-bottom: 30px;
    }}
    
    .card-header {{
        font-size: 18px;
        font-weight: 700;
        color: #1A1C1E;
        margin-bottom: 20px;
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
        
        # Проверка обязательных колонок
        for col in ['Приоритет', 'Кол-во обращений', 'Компоненты', 'Резолюция']:
            if col not in df.columns: df[col] = 'Не указано' if col != 'Кол-во обращений' else 0
            
        # Расчет TTM и Cycle Time
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки']
        work_cols = ['В работе', 'Тестирование', 'Релиз'] # Пример стадий для Cycle Time
        
        avail_ttm = [c for c in ttm_cols if c in df.columns]
        avail_work = [c for c in work_cols if c in df.columns]
        
        df['ttm_days'] = df[avail_ttm].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        df['cycle_time'] = df[avail_work].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        df['Резолюция'] = df['Резолюция'].fillna('Не указано')
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных пуста или не найдена.")
else:
    # --- САЙДБАР С ФИЛЬТРАМИ (ПОЛНЫЙ) ---
    st.sidebar.header("Настройки фильтров")
    
    db_min, db_max = df['Дата создания'].min().date(), df['Дата создания'].max().date()
    start_init = db_max - timedelta(days=db_max.weekday())
    
    date_range = st.sidebar.date_input("Период анализа", value=(start_init, db_max), min_value=db_min, max_value=db_max)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        st.sidebar.markdown("---")
        all_teams = sorted(df['Компоненты'].unique().tolist())
        select_all_t = st.sidebar.checkbox("Выбрать все команды", value=True)
        sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams if select_all_t else [])

        all_res = sorted(df['Резолюция'].unique().tolist())
        select_all_r = st.sidebar.checkbox("Выбрать все резолюции", value=True)
        sel_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res if select_all_r else [])

        # Фильтрация данных
        f_df = df[(df['Дата создания'] >= start_date) & (df['Дата создания'] <= end_date) & 
                  (df['Компоненты'].isin(sel_teams)) & (df['Резолюция'].isin(sel_res))].copy()

        # --- ЗАГОЛОВОК ---
        st.markdown('<div class="main-header">📊 Аналитика дежурств</div>', unsafe_allow_html=True)

        # --- KPI В ЯЧЕЙКАХ ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("TTM (средний)", f"{f_df['ttm_days'].mean() if not f_df.empty else 0:.2f}")
        with kpi2:
            st.metric("Cycle Time", f"{f_df['cycle_time'].mean() if not f_df.empty else 0:.2f}")
        with kpi3:
            crit_later = len(f_df[(f_df['Резолюция'] == 'Позже') & (f_df['Приоритет'] == 'Критичный')])
            st.metric("Критичные 'Позже'", crit_later)
        with kpi4:
            st.metric("Всего задач", len(f_df))

        st.markdown("<br>", unsafe_allow_html=True)

        # --- ПЕРВЫЙ РЯД ГРАФИКОВ ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-header">Нагрузка по командам</div>', unsafe_allow_html=True)
            if not f_df.empty:
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
            if not f_df.empty:
                t_avg = f_df.groupby('Компоненты')['ttm_days'].mean().reset_index()
                t_avg['Компоненты'] = pd.Categorical(t_avg['Компоненты'], categories=t_order, ordered=True)
                t_avg = t_avg.sort_values('Компоненты', ascending=False)
                fig_a = px.bar(t_avg, x='ttm_days', y='Компоненты', orientation='h', text_auto='.1f',
                               color_discrete_sequence=['#6244BB'], template="plotly_white")
                fig_a.update_traces(textposition='outside')
                fig_a.update_layout(height=400, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=0, b=0))
                st.plotly_chart(fig_a, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- ВТОРОЙ РЯД: ДИНАМИКА ---
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        dh1, dh2 = st.columns([5, 1])
        with dh1: st.markdown('<div class="card-header">📈 Динамика поступления</div>', unsafe_allow_html=True)
        with dh2: unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed", key="d_grp")
        
        if not f_df.empty:
            u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
            resampled = f_df.set_index('Дата создания').resample(u_map[unit]).size().reset_index(name='Задач')
            fig_d = px.line(resampled, x='Дата создания', y='Задач', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
            fig_d.update_layout(height=300, xaxis_title=None, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- ТРЕТИЙ РЯД: TTM И МАССОВЫЕ ---
        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-header">Распределение TTM (скорость)</div>', unsafe_allow_html=True)
            fig_h = px.histogram(f_df, x='ttm_days', nbins=20, color_discrete_sequence=['#6244BB'], template="plotly_white", marginal="violin")
            st.plotly_chart(fig_h, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c4:
            st.markdown('<div class="bi-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-header">Массовые обращения (11+)</div>', unsafe_allow_html=True)
            mass = f_df[f_df['Кол-во обращений'] >= 11]
            if not mass.empty:
                m_ch = mass.groupby('Кол-во обращений')['ttm_days'].mean().reset_index()
                fig_m = px.line(m_ch, x='Кол-во обращений', y='ttm_days', markers=True, color_discrete_sequence=['#6244BB'], template="plotly_white")
                st.plotly_chart(fig_m, use_container_width=True)
            else: st.write("Записей с обращениями 11+ не найдено.")
            st.markdown('</div>', unsafe_allow_html=True)

        # --- ПОСЛЕДНИЙ БЛОК: ОЖИДАНИЕ ---
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Процент времени до начала работы</div>', unsafe_allow_html=True)
        pre_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки']
        avail = [c for c in pre_cols if c in f_df.columns]
        f_df['pre_min'] = f_df[avail].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
        f_df['pct_wait'] = f_df.apply(lambda x: (x['pre_min'] / (x['ttm_days'] * 1440) * 100) if x['ttm_days'] > 0 else 0, axis=1)
        fig_p = px.histogram(f_df, x='pct_wait', nbins=20, color_discrete_sequence=['#A485E0'], template="plotly_white")
        st.plotly_chart(fig_p, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
