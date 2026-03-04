import streamlit as st
import pandas
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль без лишних рамок
st.markdown(
    """
    <style>
    /* Общий фон страницы */
    .stApp { background-color: #F8F9FB; }

    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: white !important;
    }

    /* Заголовки */
    .main-header { font-size: 34px; font-weight: 800; color: #1A1C1E; margin-bottom: 20px; }
    
    /* Основная карточка для графиков (единый блок) */
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    .card-header { 
        font-size: 18px; 
        font-weight: 700; 
        color: #1A1C1E; 
    }

    /* KPI карточки */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .kpi-title { 
        font-size: 15px; 
        font-weight: 600; 
        color: #1A1C1E; 
        margin-bottom: 8px; 
        display: flex; 
        align-items: center; 
    }
    .kpi-value { font-size: 32px; font-weight: 500; color: #6244BB; }

    /* Круглая серая иконка */
    .hint-icon {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 18px;
        height: 18px;
        background-color: #E6E9EF;
        color: #7E8694;
        border-radius: 50%;
        font-size: 11px;
        font-weight: bold;
        cursor: help;
        margin-left: 8px;
        position: relative;
    }

    .hint-icon:hover::after {
        content: attr(data-hint);
        position: absolute;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        background-color: #1A1C1E;
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
        width: 200px;
        z-index: 1000;
        font-weight: normal;
    }
    
    /* Убираем лишние отступы у колонок Streamlit */
    [data-testid="column"] {
        padding: 0px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str, hint: str = ""):
    hint_html = f'<span class="hint-icon" data-hint="{hint}">?</span>' if hint else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title} {hint_html}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- ЗАГРУЗКА ДАННЫХ ---
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600)
def load_data():
    if not y.exists(DB_PATH): return pd.DataFrame()
    y.download(DB_PATH, "local_view.db")
    conn = sqlite3.connect("local_view.db")
    df = pd.read_sql("SELECT * FROM tasks", conn)
    conn.close()
    if "Дата создания" not in df.columns: return pd.DataFrame()
    df["Дата создания"] = pd.to_datetime(df["Дата создания"], errors="coerce")
    df = df.dropna(subset=["Дата создания"])
    for col in ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
    df["ttm_days"] = df[["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]].sum(axis=1) / 1440
    df["cycle_time"] = df[["Бэклог разработки", "В работе"]].sum(axis=1) / 1440
    df["Резолюция"] = df.get("Резолюция", "Не указано").fillna("Не указано")
    df["Компоненты"] = df.get("Компоненты", "Не указано").fillna("Не указано")
    return df

df = load_data()

# --- САЙДБАР (ФИЛЬТРЫ) ---
st.sidebar.markdown("### Настройки")
if not df.empty:
    db_min, db_max = df["Дата создания"].min().date(), df["Дата создания"].max().date()
    date_range = st.sidebar.date_input("Период", value=(db_max - timedelta(days=7), db_max))
    sel_teams = st.sidebar.multiselect("Команды", sorted(df["Компоненты"].unique()), default=sorted(df["Компоненты"].unique()))
    
    f_df = df[(df["Дата создания"].dt.date >= date_range[0]) & 
              (df["Дата создания"].dt.date <= date_range[1]) & 
              (df["Компоненты"].isin(sel_teams))].copy()
else:
    st.stop()

# --- ВЕРСТКА ---
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

# KPI
k1, k2, k3, k4 = st.columns(4)
with k1: kpi_card("Всего задач", str(len(f_df)), "Общее количество тикетов")
with k2: kpi_card("TTM в днях", f"{f_df['ttm_days'].mean():.2f}", "Среднее время жизни задачи")
with k3: kpi_card("Cycle time", f"{f_df['cycle_time'].mean():.2f}", "Время в разработке")
with k4: kpi_card("Критичные", str(len(f_df[f_df['Резолюция']=='Позже'])), "Задачи со статусом Позже")

st.write("") # Отступ

# ГРАФИКИ
c1, c2 = st.columns(2, gap="medium")
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    # Заголовок теперь ВНУТРИ белой карточки bi-card, а не над ней
    st.markdown(
        f"""
        <div class="bi-card">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <span class="card-header">Нагрузка по командам</span>
                <span class="hint-icon" data-hint="Задачи по командам и статусам">?</span>
            </div>
        """, unsafe_allow_html=True)
    fig_l = px.bar(f_df.groupby(["Компоненты", "Резолюция"]).size().reset_index(name="Кол-во"), 
                   x="Кол-во", y="Компоненты", color="Резолюция", orientation="h",
                   category_orders={"Компоненты": t_order}, color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
    fig_l.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown(
        f"""
        <div class="bi-card">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <span class="card-header">Среднее время работы</span>
                <span class="hint-icon" data-hint="Средний TTM по каждой команде">?</span>
            </div>
        """, unsafe_allow_html=True)
    fig_a = px.bar(f_df.groupby("Компоненты")["ttm_days"].mean().reset_index(), 
                   x="ttm_days", y="Компоненты", orientation="h", text_auto=".1f",
                   color_discrete_sequence=["#6244BB"], template="plotly_white", category_orders={"Компоненты": t_order})
    fig_a.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig_a, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ДИНАМИКА
# Здесь я тоже убрал отдельную ячейку для заголовка, всё в одном блоке bi-card
st.markdown(
    f"""
    <div class="bi-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
            <div style="display: flex; align-items: center;">
                <span class="card-header">Динамика поступления задач</span>
                <span class="hint-icon" data-hint="Тренд поступления задач по времени">?</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Селектор выбора периода внутри карточки
unit = st.selectbox("Группировка", ["День", "Неделя", "Месяц"], label_visibility="collapsed")
u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
resampled = f_df.set_index("Дата создания").resample(u_map[unit]).size().reset_index(name="Задач")

fig_d = px.line(resampled, x="Дата создания", y="Задач", markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
fig_d.update_layout(height=280, margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None)
st.plotly_chart(fig_d, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)
