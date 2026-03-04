import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) Обновленный BI-стиль (Компактные плашки)
st.markdown(
    """
    <style>
    .stApp { background-color: #F7F2FA; }

    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* Единая компактная карточка */
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 16px 20px; /* Уменьшил отступы */
        box-shadow: 0 4px 10px rgba(0,0,0,0.04);
        margin-bottom: 15px;
        display: inline-block; /* Плашка теперь подстраивается под ширину контента */
        width: 100%;
    }

    .card-title-row {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        margin-bottom: 5px; /* Минимальный отступ до графика */
    }

    .card-header { 
        font-size: 18px; 
        font-weight: 700; 
        color: #1A1C1E; 
        margin: 0;
    }

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
    }

    /* KPI блоки */
    .kpi-value { font-size: 32px; font-weight: 500; color: #6244BB; margin-top: 5px; }

    /* Убираем лишние отступы Streamlit */
    [data-testid="column"] { padding: 0px 8px !important; }
    .block-container { padding-top: 1.5rem !important; }
    
    /* Скрываем лишние кнопки Plotly для чистоты */
    .modebar { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title, value, hint):
    st.markdown(f"""
        <div class="bi-card">
            <div class="card-title-row">
                <span class="card-header">{title}</span>
                <span class="hint-icon" title="{hint}">?</span>
            </div>
            <div class="kpi-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

# 3) Данные (заглушка для примера)
# Здесь должен быть твой блок загрузки df через sqlite/yadisk
data = {
    'Компоненты': ['cargo_b2b', 'udp', 'cargo_web', 'cargo_finance'],
    'Кол-во': [16, 7, 4, 3],
    'Резолюция': ['Решен', 'Решен', 'Решен', 'Решен']
}
f_df = pd.DataFrame(data)

# --- КОНТЕНТ ---
st.markdown('<h1 style="color: #1A1C1E; font-weight: 800; margin-bottom: 20px;">Аналитика дежурств</h1>', unsafe_allow_html=True)

# KPI
k1, k2, k3, k4 = st.columns(4)
with k1: kpi_card("Всего задач", "34", "Общее число задач")
with k2: kpi_card("TTM в днях", "2.14", "Среднее время")
with k3: kpi_card("Cycle time (дн)", "1.67", "Время в работе")
with k4: kpi_card("Критичные позже", "0", "Отложенные задачи")

st.write("")

# ГРАФИКИ
c1, c2 = st.columns(2)

with c1:
    # Заголовок и график на ОДНОЙ плашке
    st.markdown("""
        <div class="bi-card">
            <div class="card-title-row">
                <span class="card-header">Нагрузка по командам</span>
                <span class="hint-icon" title="Задачи по командам">?</span>
            </div>
    """, unsafe_allow_html=True)
    
    fig_l = px.bar(f_df, x="Кол-во", y="Компоненты", color="Резолюция", orientation="h",
                   color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
    fig_l.update_layout(height=300, margin=dict(l=0, r=10, t=10, b=0), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown("""
        <div class="bi-card">
            <div class="card-title-row">
                <span class="card-header">Среднее время работы</span>
                <span class="hint-icon" title="TTM по командам">?</span>
            </div>
    """, unsafe_allow_html=True)
    
    fig_a = px.bar(f_df, x="Кол-во", y="Компоненты", orientation="h",
                   color_discrete_sequence=["#6244BB"], template="plotly_white")
    fig_a.update_layout(height=300, margin=dict(l=0, r=10, t=10, b=0), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig_a, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ДИНАМИКА
st.markdown("""
    <div class="bi-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div class="card-title-row">
                <span class="card-header">Динамика поступления задач</span>
                <span class="hint-icon" title="Тренд задач">?</span>
            </div>
    """, unsafe_allow_html=True)

# Селектор внутри плашки (без лишних рамок)
unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")

# Пример графика динамики
fig_d = px.line(x=[1,2,3,4], y=[10,15,13,17], markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
fig_d.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None)
st.plotly_chart(fig_d, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
