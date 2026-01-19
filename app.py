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
        y.download(DB_PATH, "local_view.db")
        conn = sqlite3.connect("local_view.db")
        df = pd.read_sql("SELECT * FROM tasks", conn)
        conn.close()
        
        # Безопасное преобразование даты
        df['Дата создания'] = pd.to_datetime(df['Дата создания'], errors='coerce')
        df = df.dropna(subset=['Дата создания'])
        df['Дата создания'] = df['Дата создания'].dt.date
        
        # Расчет TTM
        ttm_cols = ['Сбор данных', 'Открыт', 'Заблокирован', 'На стороне менеджера', 'Бэклог разработки', 'В работе']
        available = [c for c in ttm_cols if c in df.columns]
        df['ttm_days'] = df[available].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) / 1440
        
        # Заполнение Пинг-понга
        if 'Пинг-понг обращения' in df.columns:
            df['Пинг-понг обращения'] = pd.to_numeric(df['Пинг-понг обращения'], errors='coerce').fillna(1)
            
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("База данных не найдена или пуста.")
else:
    st.title("Аналитика дежурств")

    # --- БОКОВАЯ ПАНЕЛЬ С ФИЛЬТРАМИ ---
    st.sidebar.header("Настройки фильтров")
    
    min_d = df['Дата создания'].min()
    max_d = df['Дата создания'].max()

    date_range = st.sidebar.date_input(
        "Выберите период анализа",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d
    )

    # Работаем только если выбран диапазон (две даты)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        
        # Фильтр по командам
        all_teams = sorted(df['Компоненты'].unique().tolist())
        selected_teams = st.sidebar.multiselect("Выберите команды", all_teams, default=all_teams)

        # Фильтр по резолюциям
        all_res = sorted(df['Резолюция'].unique().tolist()) if 'Резолюция' in df.columns else []
        selected_res = st.sidebar.multiselect("Выберите резолюции", all_res, default=all_res)

        # Применяем маску
        mask = (df['Дата создания'] >= start_date) & \
               (df['Дата создания'] <= end_date) & \
               (df['Компоненты'].isin(selected_teams)) & \
               (df['Резолюция'].isin(selected_res))
        
        filtered_df = df.loc[mask]

        # --- KPI МЕТРИКИ ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Всего задач", len(filtered_df))
        col2.metric("Средний TTM (дни)", f"{filtered_df['ttm_days'].mean():.2f}")
        col3.metric("Средний Пинг-понг", f"{filtered_df['Пинг-понг обращения'].mean():.1f}")

        st.markdown("---")

        # --- ГОРИЗОНТАЛЬНЫЙ ГРАФИК НАГРУЗКИ (На всю ширину) ---
        st.subheader("Нагрузка по командам и резолюциям")
        
        if not filtered_df.empty:
            # Группировка для стекового графика
            team_res_counts = filtered_df.groupby(['Компоненты', 'Резолюция']).size().reset_index(name='Кол-во')
            
            # Сортировка команд по общему кол-ву задач
            team_order = filtered_df['Компоненты'].value_counts().index.tolist()

            fig_team = px.bar(
                team_res_counts, 
                x='Кол-во', 
                y='Компоненты', 
                color='Резолюция',
                orientation='h',
                text='Кол-во',
                category_orders={"Компоненты": team_order},
                # Указываем приятные цвета для основных статусов
                color_discrete_map={"Решен": "#2a9d8f", "Позже": "#e9c46a", "Отклонен": "#e76f51"},
                template="seaborn"
            )

            fig_team.update_layout(
                height=max(400, len(team_order) * 35), # Автоподбор высоты под кол-во команд
                xaxis_title="Количество задач",
                yaxis_title=None,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_team, use_container_width=True)
        else:
            st.warning("Нет данных для отображения по выбранным фильтрам")

        st.markdown("---")

        # --- ВТОРОСТЕПЕННЫЕ ГРАФИКИ (В две колонки) ---
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Динамика поступления")
            date_counts = filtered_df.groupby('Дата создания').size().reset_index(name='Задач')
            fig_date = px.line(date_counts, x='Дата создания', y='Задач', markers=True)
            st.plotly_chart(fig_date, use_container_width=True)

        with c2:
            st.subheader("Распределение TTM")
            fig_ttm = px.histogram(filtered_df, x='ttm_days', nbins=20, 
                                   color_discrete_sequence=['#457b9d'], marginal="violin")
            st.plotly_chart(fig_ttm, use_container_width=True)


    else:
        st.info("Выберите начальную и конечную даты в календаре слева.")

    # Кнопка обновления
    if st.sidebar.button('🔄 Обновить базу данных'):
        st.cache_data.clear()
        st.rerun()
