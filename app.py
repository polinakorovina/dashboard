import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os

# 1. Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# --- ИНДИВИДУАЛЬНЫЙ СТИЛЬ (Фиолетовая тема) ---
st.markdown(f"""
    <style>
    /* 1. Цвет фона боковой панели */
    [data-testid="stSidebar"] {{
        background-color: #f3f0f7;
    }}

    /* 2. Радиокнопки (точки выбора периода) */
    /* Ободок активной кнопки */
    div[data-testid="stRadio"] [data-testid="stWidgetLabel"] + div div[role="radiogroup"] div[data-baseweb="radio"] div:first-child {{
        border-color: #9f86c0 !important;
    }}
    /* Внутренняя точка активной кнопки */
    div[role="radiogroup"] div[data-baseweb="radio"] div:first-child div:nth-child(2) {{
        background-color: #9f86c0 !important;
    }}

    /* 3. Чекбоксы (галочки "Выбрать всё") */
    /* Фон квадратика при нажатии */
    div[data-testid="stCheckbox"] input[type="checkbox"]:checked + div {{
        border-color: #9f86c0 !important;
    }}
    /* Цвет самой галочки внутри */
    div[data-testid="stCheckbox"] svg {{
        fill: white !important;
    }}

    /* 4. Мультиселект (Теги выбранных команд) */
    /* Цвет фона плашки (тега) */
    span[data-baseweb="tag"] {{
        background-color: #9f86c0 !important;
    }}
    /* Убираем красный цвет при наведении на крестик в теге */
    span[data-baseweb="tag"] span[role="button"]:hover {{
        background-color: #5e548e !important;
    }}

    /* 5. Календарь и общие акценты */
    :root {{
        --primary-color: #9f86c0;
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
        
        # Расчет TTM и чистка данных
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        if 'Пинг-понг обращения' in df.columns:
            df['Пинг-понг обращения'] = pd.to_numeric(df['Пинг-понг обращения'], errors='coerce').fillna(1)
        
        df['Резолюция'] = df['Резолюция'].fillna('Не указано') if 'Резолюция' in df.columns else 'Не указано'
            
        return df
    return pd.DataFrame()

df = load_data()

from datetime import datetime, timedelta

# Находим текущую дату и начало недели (понедельник)
today = datetime.now().date()
start_of_week = today - timedelta(days=today.weekday())

# Берем крайние даты из базы для ограничений календаря
db_min_date = df['Дата создания'].min().date()
db_max_date = df['Дата создания'].max().date()


if df.empty:
    st.error("База данных не найдена или пуста.")
else:
    st.title("Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ С ФИЛЬТРАМИ ---
    st.sidebar.header("Настройки фильтров")
    
    # Фильтр дат
    min_d = df['Дата создания'].min().date()
    max_d = df['Дата создания'].max().date()
    date_range = st.sidebar.date_input(
    "Период анализа", 
    value=(start_of_week, db_max_date), # Вот здесь магия: ставим понедельник
    min_value=db_min_date,             # Но разрешаем листать до начала времен
    max_value=db_max_date
)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        # Группировка времени (День, Неделя, Месяц, Год)
        st.sidebar.markdown("---")
        time_unit = st.sidebar.radio(
            "Группировка динамики поступления:",
            ('День', 'Неделя', 'Месяц', 'Год'),
            index=0
        )
        # Маппинг для Pandas: D=Day, W=Week, ME=Month End, YE=Year End
        unit_map = {'День': 'D', 'Неделя': 'W', 'Месяц': 'ME', 'Год': 'YE'}

        # Чекбоксы выбора всего
        st.sidebar.markdown("---")
        all_teams = sorted(df['Компоненты'].unique().tolist())
        select_all_teams = st.sidebar.checkbox("Выбрать все команды", value=True)
        selected_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams if select_all_teams else [])

        all_res = sorted(df['Резолюция'].unique().tolist())
        select_all_res = st.sidebar.checkbox("Выбрать все резолюции", value=True)
        selected_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res if select_all_res else [])

        # Фильтрация
        mask = (df['Дата создания'] >= start_date) & \
               (df['Дата создания'] <= end_date) & \
               (df['Компоненты'].isin(selected_teams)) & \
               (df['Резолюция'].isin(selected_res))
        f_df = df.loc[mask].copy()

        # --- KPI ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Всего задач", len(f_df))
        col2.metric("Средний TTM (дни)", f"{f_df['ttm_days'].mean():.2f}")
        col3.metric("Средний Пинг-понг", f"{f_df['Пинг-понг обращения'].mean():.1f}")

        st.markdown("---")

        # --- ГРАФИК НАГРУЗКИ (Горизонтальный) ---
        st.subheader("Нагрузка по командам")
        if not f_df.empty:
            team_order = f_df['Компоненты'].value_counts().index.tolist()
            fig_team = px.bar(
                f_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во'),
                x='Кол-во', y='Компоненты', color='Резолюция',
                orientation='h', text='Кол-во',
                category_orders={"Компоненты": team_order},
                color_discrete_map={"Решен": "#5e548e", "Позже": "#be95c4"},
                template="seaborn"
            )
            # НАСТРОЙКИ ОТОБРАЖЕНИЯ:
            fig_team.update_layout(
                height=max(400, len(team_order) * 40), 
                margin=dict(t=20, r=150), # Добавили отступ справа (r=150) для легенды
                legend=dict(
                    orientation="v",      # Вертикальная легенда
                    yanchor="middle", 
                    y=0.5,                # Центрируем по вертикали
                    xanchor="left", 
                    x=1.02                # Сдвигаем чуть правее границы графика
                ),
                xaxis_title="Количество задач",
                yaxis_title=None
            )
            st.plotly_chart(fig_team, use_container_width=True)
        
        st.markdown("---")

        st.markdown("---")

        # --- ДИНАМИКА ПОСТУПЛЕНИЯ С ГРУППИРОВКОЙ ---
        st.subheader(f"📈 Динамика поступления (по {time_unit.lower()})")
        if not f_df.empty:
            # Важный момент: resample работает только если индекс - это дата
            resampled_data = f_df.set_index('Дата создания').resample(unit_map[time_unit]).size().reset_index(name='Задач')
            
            fig_date = px.line(resampled_data, x='Дата создания', y='Задач', markers=True)
            st.plotly_chart(fig_date, use_container_width=True)

        # --- TTM ГИСТОГРАММА ---
        st.subheader("Распределение скорости решения (TTM)")
        fig_ttm = px.histogram(f_df, x='ttm_days', nbins=20, color_discrete_sequence=['#457b9d'], marginal="violin")
        st.plotly_chart(fig_ttm, use_container_width=True)

    
    else:
        st.info("💡 Выберите диапазон дат в левом меню.")
