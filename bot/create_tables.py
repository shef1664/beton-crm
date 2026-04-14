"""
Скрипт создания Google-таблиц для PULSAR.
Создаёт 5 таблиц с нужными листами и заголовками колонок.
Запуск: python create_tables.py
"""

import json
import os
from google.oauth2.service_account import Credentials
import gspread

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json.json")

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════

TABLES_CONFIG = [
    {
        "name": "PULSAR_Рейсы_Тонары",
        "sheets": [
            {
                "title": "Рейсы",
                "headers": [
                    "ID", "Дата", "Время", "Водитель", "Машина",
                    "Карьер", "Материал", "Фракция",
                    "Заказчик", "Объект",
                    "Тоннаж_загрузка", "Тоннаж_выгрузка",
                    "ТН_фото_лиц", "ТН_фото_оборот",
                    "Статус", "Стоимость_рейса", "Комментарий"
                ]
            }
        ]
    },
    {
        "name": "PULSAR_Рейсы_Миксеры",
        "sheets": [
            {
                "title": "Рейсы",
                "headers": [
                    "ID", "Дата", "Время_прибытия", "Время_убытия",
                    "Водитель", "Машина",
                    "Завод", "Тип_смеси", "Марка", "ПМД", "Температура_ПМД",
                    "Объём_м3", "Заказчик", "Адрес",
                    "Стоимость_бетона", "Стоимость_доставки",
                    "Тип_расчёта", "Деньги_у", "Номер_ТН",
                    "Фото_ТН", "Фото_рапорт", "Комментарий"
                ]
            }
        ]
    },
    {
        "name": "PULSAR_Рейсы_Длинномеры",
        "sheets": [
            {
                "title": "Рейсы",
                "headers": [
                    "ID", "Дата", "Водитель", "Машина",
                    "Маршрут_от", "Маршрут_до", "Груз",
                    "ТН_фото", "Статус", "Комментарий"
                ]
            },
            {
                "title": "Топливо",
                "headers": [
                    "ID", "Дата", "Машина", "Литры",
                    "Стоимость", "Цена_за_литр", "АЗС",
                    "Фото_чека", "Комментарий"
                ]
            },
            {
                "title": "Расходы",
                "headers": [
                    "ID", "Дата", "Категория", "Сумма",
                    "Описание", "Фото", "Комментарий"
                ]
            },
            {
                "title": "Ремонты",
                "headers": [
                    "ID", "Дата", "Машина", "Тип_ремонта",
                    "Описание", "Запчасти", "Стоимость",
                    "Статус", "Мастер", "Комментарий"
                ]
            },
            {
                "title": "Запчасти",
                "headers": [
                    "ID", "Дата", "Название", "Количество",
                    "Цена", "Оплата", "Долг", "Комментарий"
                ]
            }
        ]
    },
    {
        "name": "PULSAR_Зарплата_Слесарь",
        "sheets": [
            {
                "title": "Учёт",
                "headers": [
                    "ID", "Дата", "Тип",
                    "Смена_выход", "Аванс_сумма",
                    "Заправка_литры", "Заправка_стоимость", "Заправка_АЗС",
                    "Ставка", "Комментарий"
                ]
            }
        ]
    },
    {
        "name": "PULSAR_Планы_Директора",
        "sheets": [
            {
                "title": "Цены_Рейсов",
                "headers": [
                    "ID", "Водитель", "Карьер", "Заказчик",
                    "Стоимость", "Дата_создания", "Активно"
                ]
            },
            {
                "title": "Планы_Карьеров",
                "headers": [
                    "ID", "Карьер", "Тоннаж_план", "Период",
                    "Тоннаж_факт", "Прогресс_%", "Дата_создания", "Активно"
                ]
            }
        ]
    }
]


def main():
    # Авторизация
    with open(CREDS_FILE, "r", encoding="utf-8") as f:
        creds_data = json.load(f)

    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    client = gspread.authorize(creds)

    created = []

    for table_cfg in TABLES_CONFIG:
        print(f"\n📋 Создаём таблицу: {table_cfg['name']}")

        # Создать Spreadsheet
        try:
            spreadsheet = client.create(table_cfg["name"])
        except gspread.exceptions.APIError as e:
            print(f"   ⚠️ Ошибка: {e}")
            continue

        spreadsheet_id = spreadsheet.id
        spreadsheet_url = spreadsheet.url
        service_email = creds_data["client_email"]

        # Поделиться с владельцем (сервисный аккаунт уже владелец)
        print(f"   ✅ Создана: {spreadsheet_url}")
        print(f"   📧 Service Account: {service_email}")

        # Создать листы
        for i, sheet_cfg in enumerate(table_cfg["sheets"]):
            if i == 0:
                # Переименовать первый лист
                sheet = spreadsheet.sheet1
                sheet.update_title(sheet_cfg["title"])
            else:
                sheet = spreadsheet.add_worksheet(
                    title=sheet_cfg["title"],
                    rows=1000,
                    cols=len(sheet_cfg["headers"])
                )

            # Записать заголовки
            headers = sheet_cfg["headers"]
            sheet.update("A1:" + chr(64 + len(headers)) + "1", [headers])

            # Форматирование заголовков (жирный)
            sheet.format("A1:" + chr(64 + len(headers)) + "1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.12, "green": 0.12, "blue": 0.18},
                "foregroundColor": {"red": 0.94, "green": 0.93, "blue": 1.0}
            })

            # Закрепить первую строку
            sheet.batch_update({
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet.id,
                            "gridProperties": {"frozenRowCount": 1}
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                }]
            })

            print(f"   📄 Лист '{sheet_cfg['title']}: {len(headers)} колонок")

        created.append({
            "name": table_cfg["name"],
            "id": spreadsheet_id,
            "url": spreadsheet_url
        })

    # Итог
    print("\n" + "=" * 60)
    print("✅ ГОТОВО! Созданные таблицы:")
    print("=" * 60)

    for t in created:
        print(f"\n📊 {t['name']}")
        print(f"   ID: {t['id']}")
        print(f"   URL: {t['url']}")

    # Сохранить ID в файл
    output = {t["name"]: t["id"] for t in created}
    output_file = os.path.join(os.path.dirname(__file__), "spreadsheet_ids.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n💾 ID сохранены в: {output_file}")
    print("\n⚠️ ВАЖНО: Дай доступ сервисному аккаунту к таблицам:")
    print(f"   📧 {service_email}")


if __name__ == "__main__":
    main()
