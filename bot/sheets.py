"""
Модуль записи данных в Google Sheets для PULSAR.
5 отдельных таблиц с разными листами.
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from config import SPREADSHEETS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None

def get_client():
    global _client
    if _client is None:
        # Попробовать credentials из env или файла
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if creds_json:
            import json
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
        else:
            creds_file = os.path.join(os.path.dirname(__file__), "credentials.json.json")
            if not os.path.exists(creds_file):
                creds_file = os.path.join(os.path.dirname(__file__), "credentials.json")
            creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_sheet(table_key, sheet_name):
    """Получить лист по ключу таблицы и имени листа."""
    client = get_client()
    ss_id = SPREADSHEETS.get(table_key)
    if not ss_id:
        raise ValueError(f"Таблица '{table_key}' не найдена в конфигурации")
    ss = client.open_by_key(ss_id)
    return ss.worksheet(sheet_name)


def append_row_safe(sheet, values):
    """Добавить строку, гарантируя что заголовки есть."""
    if not sheet.row_values(1):
        raise ValueError(f"Лист '{sheet.title}' пуст — нет заголовков")
    sheet.append_row(values)


# ═══════════════════════════════════════════
# 1. РЕЙСЫ_ТОНАРЫ
# ═══════════════════════════════════════════

def save_tonar_trip(data):
    """Сохранить рейс тонара.
    Колонки: ID, Дата, Время, Водитель, Машина, Карьер, Материал, Фракция,
             Заказчик, Объект, Тоннаж_загрузка, Тоннаж_выгрузка,
             ТН_фото_лиц, ТН_фото_оборот, Статус, Стоимость_рейса, Комментарий
    """
    sheet = get_sheet("PULSAR_Рейсы_Тонары", "Рейсы")
    row_id = f"TNR-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id,
        data.get("date", ""),
        data.get("time", ""),
        data.get("driver", ""),
        data.get("truck", ""),
        data.get("quarry", ""),
        data.get("material", ""),
        data.get("fraction", ""),
        data.get("client", ""),
        data.get("object", ""),
        data.get("load_tonnage", ""),
        data.get("unload_tonnage", ""),
        data.get("tn_front", ""),
        data.get("tn_back", ""),
        data.get("status", "ok"),
        data.get("price", ""),
        data.get("comment", ""),
    ])
    return row_id


# ═══════════════════════════════════════════
# 2. РЕЙСЫ_МИКСЕРЫ
# ═══════════════════════════════════════════

def save_mixer_trip(data):
    """Сохранить рейс миксера.
    Колонки: ID, Дата, Время_прибытия, Время_убытия, Водитель, Машина,
             Завод, Тип_смеси, Марка, ПМД, Температура_ПМД, Объём_м3,
             Заказчик, Адрес, Стоимость_бетона, Стоимость_доставки,
             Тип_расчёта, Деньги_у, Номер_ТН, Фото_ТН, Фото_рапорт, Комментарий
    """
    sheet = get_sheet("PULSAR_Рейсы_Миксеры", "Рейсы")
    row_id = f"MIX-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id,
        data.get("date", ""),
        data.get("arrive_time", ""),
        data.get("depart_time", ""),
        data.get("driver", ""),
        data.get("truck", ""),
        data.get("plant", ""),
        data.get("mix_type", ""),
        data.get("grade", ""),
        data.get("pmd", "Нет"),
        data.get("pmd_temp", ""),
        data.get("volume", ""),
        data.get("client", ""),
        data.get("address", ""),
        data.get("concrete_cost", ""),
        data.get("delivery_cost", ""),
        data.get("payment_type", ""),
        data.get("money_with", ""),
        data.get("tn_number", ""),
        data.get("tn_photo", ""),
        data.get("report_photo", ""),
        data.get("comment", ""),
    ])
    return row_id


# ═══════════════════════════════════════════
# 3. РЕЙСЫ_ДЛИННОМЕРЫ
# ═══════════════════════════════════════════

def save_dlinn_trip(data):
    """Рейс длинномера. Колонки: ID, Дата, Водитель, Машина,
       Маршрут_от, Маршрут_до, Груз, ТН_фото, Статус, Комментарий"""
    sheet = get_sheet("PULSAR_Рейсы_Длинномеры", "Рейсы")
    row_id = f"DLN-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id, data.get("date",""), data.get("driver",""), data.get("truck",""),
        data.get("from",""), data.get("to",""), data.get("cargo",""),
        data.get("tn_photo",""), data.get("status","ok"), data.get("comment",""),
    ])
    return row_id


def save_dlinn_fuel(data):
    """Топливо длинномера. Колонки: ID, Дата, Машина, Литры, Стоимость, Цена_за_литр, АЗС, Фото_чека, Комментарий"""
    sheet = get_sheet("PULSAR_Рейсы_Длинномеры", "Топливо")
    row_id = f"FUL-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id, data.get("date",""), data.get("truck",""), data.get("liters",""),
        data.get("cost",""), data.get("price_per_liter",""), data.get("station",""),
        data.get("receipt_photo",""), data.get("comment",""),
    ])
    return row_id


def save_dlinn_expense(data):
    """Расход длинномера. Колонки: ID, Дата, Категория, Сумма, Описание, Фото, Комментарий"""
    sheet = get_sheet("PULSAR_Рейсы_Длинномеры", "Расходы")
    row_id = f"EXP-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id, data.get("date",""), data.get("category",""), data.get("amount",""),
        data.get("description",""), data.get("photo",""), data.get("comment",""),
    ])
    return row_id


def save_dlinn_repair(data):
    """Ремонт. Колонки: ID, Дата, Машина, Тип_ремонта, Описание, Запчасти, Стоимость, Статус, Мастер, Комментарий"""
    sheet = get_sheet("PULSAR_Рейсы_Длинномеры", "Ремонты")
    row_id = f"REP-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id, data.get("date",""), data.get("truck",""), data.get("repair_type",""),
        data.get("description",""), data.get("parts",""), data.get("cost",""),
        data.get("status","open"), data.get("mechanic",""), data.get("comment",""),
    ])
    return row_id


def save_dlinn_parts(data):
    """Запчасти. Колонки: ID, Дата, Название, Количество, Цена, Оплата, Долг, Комментарий"""
    sheet = get_sheet("PULSAR_Рейсы_Длинномеры", "Запчасти")
    row_id = f"PRT-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id, data.get("date",""), data.get("name",""), data.get("quantity",""),
        data.get("price",""), data.get("payment",""), data.get("debt",""),
        data.get("comment",""),
    ])
    return row_id


# ═══════════════════════════════════════════
# 4. ЗАРПЛАТА_СЛЕСАРЬ
# ═══════════════════════════════════════════

def save_mechanic_record(data):
    """Запись слесаря. Колонки: ID, Дата, Тип, Смена_выход, Аванс_сумма,
       Заправка_литры, Заправка_стоимость, Заправка_АЗС, Ставка, Комментарий"""
    sheet = get_sheet("PULSAR_Зарплата_Слесарь", "Учёт")
    row_id = f"MCH-{len(sheet.get_all_values())}"
    rec_type = data.get("type", "shift")  # shift, advance, fuel
    append_row_safe(sheet, [
        row_id,
        data.get("date", ""),
        rec_type,
        "Да" if rec_type == "shift" else "",
        data.get("advance_amount", "") if rec_type == "advance" else "",
        data.get("fuel_liters", "") if rec_type == "fuel" else "",
        data.get("fuel_cost", "") if rec_type == "fuel" else "",
        data.get("fuel_station", "") if rec_type == "fuel" else "",
        data.get("rate", "6000"),
        data.get("comment", ""),
    ])
    return row_id


# ═══════════════════════════════════════════
# 5. ПЛАНЫ_ДИРЕКТОРА
# ═══════════════════════════════════════════

def save_director_trip_price(data):
    """Цена рейса. Колонки: ID, Водитель, Карьер, Заказчик, Стоимость, Дата_создания, Активно"""
    sheet = get_sheet("PULSAR_Планы_Директора", "Цены_Рейсов")
    row_id = f"PRC-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id,
        data.get("driver", ""),
        data.get("quarry", ""),
        data.get("client", ""),
        data.get("price", ""),
        data.get("created_at", ""),
        "Да",
    ])
    return row_id


def save_director_quarry_plan(data):
    """План карьера. Колонки: ID, Карьер, Тоннаж_план, Период, Тоннаж_факт, Прогресс_%, Дата_создания, Активно"""
    sheet = get_sheet("PULSAR_Планы_Директора", "Планы_Карьеров")
    row_id = f"PLN-{len(sheet.get_all_values())}"
    append_row_safe(sheet, [
        row_id,
        data.get("quarry", ""),
        data.get("planned_tonnage", ""),
        data.get("period", ""),
        "0",
        "0%",
        data.get("created_at", ""),
        "Да",
    ])
    return row_id


# ═══════════════════════════════════════════
# ЧТЕНИЕ ДАННЫХ
# ═══════════════════════════════════════════

def read_sheet(table_key, sheet_name):
    """Прочитать все данные из листа."""
    sheet = get_sheet(table_key, sheet_name)
    return sheet.get_all_records()
