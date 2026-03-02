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
        background-color: #6244BB;
    }}
    [data-testid="stSidebar"] {{
        color: white;
    }}
    /* Цвет заголовков в боковой панели */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stMarkdown {{
        color: white;
    }}

    /* 2. Радиокнопки (точки выбора периода) */
    div[role="radiogroup"] div[data-baseweb="radio"] div:first-child {{
        border-color: #6244BB !important;
    }}
    div[role="radiogroup"] div[data-baseweb="radio"] div:first-child div:nth-child(2) {{
        background-color: #6244BB !important;
    }}

    /* 3. Чекбоксы */
    div[data-testid="stCheckbox"] input[type="checkbox"]:checked + div {{
        border-color: #6244BB !important;
    }}
    div[data-testid="stCheckbox"] svg {{
        fill: white !important;
    }}

    /* 4. Мультиселект (Теги) */
    span[data-baseweb="tag"] {{
        background-color: #6244BB !important;
    }}
    
    /* 5. Календарь и общие акценты */
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
        
        # Преобразование даты
        df['Дата создания'] = pd.to_datetime(df['Дата создания'], errors='coerce')
        df = df.dropna(subset=['Дата создания'])
        
        # Гарантируем наличие важных колонок, чтобы код не падал
        if 'Приоритет' not in df.columns:
            df['Приоритет'] = 'Не указан'
        if 'Кол-во обращений' not in df.columns:
            df['Кол-во обращений'] = 0
        if 'Ключ' not in df.columns:
            df['Ключ'] = 'Unknown'
            
        # Расчет TTM
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        if 'Пинг-понг обращения' in df.columns:
            df['Пинг-понг обращения'] = pd.to_numeric(df['Пинг-понг обращения'], errors='coerce').fillna(1)
        
        df['Резолюция'] = df['Резолюция'].fillna('Не указано') if 'Резолюция' in df.columns else 'Не указано'
            
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных не найдена или пуста.")
else:
    # Определение границ дат
    last_date_in_db = df['Дата создания'].max().date()
    start_of_last_week = last_date_in_db - timedelta(days=last_date_in_db.weekday())
    db_min_date = df['Дата создания'].min().date()
    db_max_date = last_date_in_db

    st.title("Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ С ФИЛЬТРАМИ ---
    st.sidebar.header("Настройки фильтров")
    
    date_range = st.sidebar.date_input(
        "Период анализа", 
        value=(start_of_last_week, db_max_date), 
        min_value=db_min_date,
        max_value=db_max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        # Группировка времени
        st.sidebar.markdown("---")
        time_unit = st.sidebar.radio(
            "Группировка динамики поступления:",
            ('День', 'Неделя', 'Месяц', 'Год'),
            index=0
        )
        unit_map = {'День': 'D', 'Неделя': 'W', 'Месяц': 'ME', 'Год': 'YE'}

        # Выбор команд и резолюций
        st.sidebar.markdown("---")
        all_teams = sorted(df['Компоненты'].unique().tolist())
        select_all_teams = st.sidebar.checkbox("Выбрать все команды", value=True)
        selected_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams if select_all_teams else [])

        all_res = sorted(df['Резолюция'].unique().tolist())
        select_all_res = st.sidebar.checkbox("Выбрать все резолюции", value=True)
        selected_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res if select_all_res else [])

        # Фильтрация данных
        mask = (df['Дата создания'] >= start_date) & \
               (df['Дата создания'] <= end_date) & \
               (df['Компоненты'].isin(selected_teams)) & \
               (df['Резолюция'].isin(selected_res))
        f_df = df.loc[mask].copy()

        # === БЕЗОПАСНЫЙ РАСЧЕТ КРИТИЧНЫХ ЗАДАЧ ===
        priority_mask = (f_df['Резолюция'] == 'Позже') & (f_df['Приоритет'] == 'Критичный')
        priority_later_df = f_df[priority_mask].copy()
        total_priority_later = len(priority_later_df)

        # --- KPI ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Всего задач", len(f_df))
        
        avg_ttm = f_df['ttm_days'].mean() if not f_df.empty else 0
        col2.metric("Средний TTM (дни)", f"{avg_ttm:.2f}")
        
        col3.metric("Критичные с рез. 'Позже'", total_priority_later)

        st.markdown("---")

        # --- ГРАФИК НАГРУЗКИ ---
        st.subheader("Нагрузка по командам")
        if not f_df.empty:
            team_order = f_df['Компоненты'].value_counts().index.tolist()
            fig_team = px.bar(
                f_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во'),
                x='Кол-во', y='Компоненты', color='Резолюция',
                orientation='h', text='Кол-во',
                category_orders={"Компоненты": team_order},
                color_discrete_map={"Решен": "#6244BB", "Позже": "#5e548e"},
                template="seaborn"
            )
            fig_team.update_layout(
                height=max(400, len(team_order) * 40), 
                margin=dict(t=20, r=150),
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
                xaxis_title="Количество задач",
                yaxis_title=None
            )
            st.plotly_chart(fig_team, use_container_width=True)
        
        st.markdown("---")

        # --- ДИНАМИКА ПОСТУПЛЕНИЯ ---
        st.subheader(f"📈 Динамика поступления (по {time_unit.lower()})")
        if not f_df.empty:
            resampled_data = f_df.set_index('Дата создания').resample(unit_map[time_unit]).size().reset_index(name='Задач')
            fig_date = px.line(resampled_data, x='Дата создания', y='Задач', markers=True, color_discrete_sequence=['#6244BB'])
            st.plotly_chart(fig_date, use_container_width=True)

        # --- TTM ГИСТОГРАММА ---
        st.subheader("Распределение скорости решения (TTM)")
        if not f_df.empty:
            fig_ttm = px.histogram(f_df, x='ttm_days', nbins=20, color_discrete_sequence=['#6244BB'], marginal="violin")
            st.plotly_chart(fig_ttm, use_container_width=True)

        st.markdown("---")

        # --- ДОПОЛНИТЕЛЬНЫЕ МЕТРИКИ ---
        
        # 1. Массовые обращения
        st.subheader("Массовые обращения (11+)")
        mass_mask = f_df['Кол-во обращений'] >= 11
        if any(mass_mask):
            mass_issues = f_df[mass_mask].groupby('Кол-во обращений')['ttm_days'].mean().reset_index()
            mass_issues['Кол-во обращений_str'] = mass_issues['Кол-во обращений'].apply(lambda x: f"{int(x)}+")
            fig_mass_issues = px.line(mass_issues, x='Кол-во обращений_str', y='ttm_days', markers=True, title="Среднее время решения массовых обращений", color_discrete_sequence=['#6244BB'])
            st.plotly_chart(fig_mass_issues, use_container_width=True)
        else:
            st.write("Массовых обращений за этот период не найдено.")

        # 2. Время работы команды
        st.subheader("Среднее время работы по командам")
        if not f_df.empty:
            team_work_time = f_df.groupby('Компоненты').agg({'ttm_days': 'mean'}).sort_values('ttm_days', ascending=False).reset_index()
            fig_team_work_time = px.bar(team_work_time, x='Компоненты', y='ttm_days', color_discrete_sequence=['#6244BB'])
            st.plotly_chart(fig_team_work_time, use_container_width=True)

        # 3. Загрузка команды
        st.subheader("Количество задач по командам (динамика)")
        if not f_df.empty:
            team_workload = f_df.groupby('Компоненты').size().reset_index(name='Кол-во задач').sort_values('Кол-во задач', ascending=False)
            fig_team_workload = px.bar(team_workload, x='Компоненты', y='Кол-во задач', color_discrete_sequence=['#5e548e'])
            st.plotly_chart(fig_team_workload, use_container_width=True)

        # 4. Процент времени до работы
        st.subheader("Процент времени до начала работы")
        if not f_df.empty:
            # Считаем сумму "предварительных" стадий
            pre_work_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки']
            available_pre = [c for c in pre_work_cols if c in f_df.columns]
            
            f_df['pre_work_min'] = f_df[available_pre].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1)
            # Избегаем деления на 0: считаем процент только если ttm_days > 0
            f_df['percent_before'] = f_df.apply(lambda x: (x['pre_work_min'] / (x['ttm_days'] * 1440) * 100) if x['ttm_days'] > 0 else 0, axis=1)
            
            fig_time_before = px.histogram(f_df, x='percent_before', nbins=20, title="Распределение времени ожидания до начала работы (%)", color_discrete_sequence=['#6244BB'])
            st.plotly_chart(fig_time_before, use_container_width=True)
    
    else:
        st.info("💡 Выберите диапазон дат в левом меню.")
