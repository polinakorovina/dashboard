import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы и фона
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #F7F2FA; } /* Светло-фиолетовый фон */
    
    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* Единая карточка (плашка) */
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    .card-header { 
        font-size: 18px; 
        font-weight: 700; 
        color: #1A1C1E; 
    }

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
    
    /* Тултип */
    .hint-icon:hover::after {
        content: attr(data-hint);
        position: absolute;
        bottom: 125%; left: 50%; transform: translateX(-50%);
        background-color: #1A1C1E; color: #fff;
        padding: 8px 12px; border-radius: 8px;
        font-size: 12px; width: 200px; z-index: 1000;
        font-weight: normal; line-height: 1.3;
    }

    /* KPI блоки */
    .kpi-title { font-size: 15px; font-weight: 600; color: #1A1C1E; margin-bottom: 8px; display: flex; align-items: center; }
    .kpi-value { font-size: 32px; font-weight: 500; color: #6244BB; }

    /* Убираем лишние отступы Streamlit внутри колонок */
    [data-testid="column"] { padding: 0px 10px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# Функция для KPI
def kpi_card(title, value, hint):
    st.markdown(f"""
        <div class="bi-card">
            <div class="kpi-title">{title} <span class="hint-icon" data-hint="{hint}">?</span></div>
            <div class="kpi-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

# --- ЗАГРУЗКА ДАННЫХ (заглушка/логика) ---
# ... (твой код загрузки df) ...

# --- ВЕРСТКА ---
st.markdown('<h1 style="color: #1A1C1E; font-weight: 800; margin-bottom: 20px;">Аналитика дежурств</h1>', unsafe_allow_html=True)

# Блок KPI
k1, k2, k3, k4 = st.columns(4)
with k1: kpi_card("Всего задач", "34", "Общее количество задач")
with k2: kpi_card("TTM в днях", "2.14", "Среднее время выполнения")
with k3: kpi_card("Cycle time (дн)", "1.67", "Время активной работы")
with k4: kpi_card("Критичные позже", "0", "Криты в статусе Позже")

# Блок ГРАФИКОВ (Нагрузка и Время)
c1, c2 = st.columns(2)

with c1:
    # ОТКРЫВАЕМ ПЛАШКУ
    st.markdown(f"""
        <div class="bi-card">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span class="card-header">Нагрузка по командам</span>
                <span class="hint-icon" data-hint="Кол-во задач по каждой команде">?</span>
            </div>
    """, unsafe_allow_html=True)
    
    # РИСУЕМ ГРАФИК (он окажется внутри этой же плашки)
    # fig_l = px.bar(...) 
    st.plotly_chart(fig_l, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True) # ЗАКРЫВАЕМ ПЛАШКУ

with c2:
    st.markdown(f"""
        <div class="bi-card">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span class="card-header">Среднее время работы</span>
                <span class="hint-icon" data-hint="Сколько дней в среднем работают команды">?</span>
            </div>
    """, unsafe_allow_html=True)
    
    # st.plotly_chart(fig_a, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Блок ДИНАМИКИ
st.markdown(f"""
    <div class="bi-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <div style="display: flex; align-items: center;">
                <span class="card-header">Динамика поступления задач</span>
                <span class="hint-icon" data-hint="График новых задач по времени">?</span>
            </div>
    """, unsafe_allow_html=True)

# Селектор выбора периода (будет внутри плашки над графиком)
unit = st.selectbox("Группировка", ["День", "Неделя", "Месяц"], label_visibility="collapsed")

# st.plotly_chart(fig_d, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
