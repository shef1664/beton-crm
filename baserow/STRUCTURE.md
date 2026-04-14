# 📊 Структура Baserow

## Таблица 1: leads (Лиды)

| Поле | Тип | Описание |
|------|-----|----------|
| name | Text | Имя клиента |
| phone | Text | Телефон |
| source | Text | Источник: landing, telegram, phone |
| concrete_grade | Text | Марка бетона (М100-М450) |
| volume | Number | Объём в м³ |
| address | Text | Адрес доставки |
| delivery_date | Text | Дата доставки |
| urgency | Text | Срочность: normal, urgent, today |
| payment_method | Text | Способ оплаты |
| comment | Long text | Комментарий |
| calculated_amount | Number | Расчётная сумма |
| distance | Number | Расстояние в км |
| client_type | Text | private или company |
| created_at | Date | Дата создания |
| lead_id | Number | ID лида в amoCRM |
| status | Text | Статус обработки |

---

## Таблица 2: logs (Логи)

| Поле | Тип | Описание |
|------|-----|----------|
| action | Text | Действие: create_lead, calculate, error |
| error | Long text | Текст ошибки |
| data | Long text | Данные запроса (до 1000 символов) |
| timestamp | Date | Время события |

---

## Как создать

1. Зайдите на https://baserow.io
2. Создайте новую базу
3. Переименуйте "Table 1" в "leads"
4. Добавьте поля согласно таблице выше
5. Создайте вторую таблицу "logs"
6. В Settings → API Access скопируйте Token
7. Вставьте ID таблиц и Token в `.env` файл
