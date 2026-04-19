# Схема Отдела Продаж и amoCRM

## Цель

Собрать все источники лидов в один контур:

`Источник -> backend -> amoCRM -> отдел продаж -> аналитика`

## Источники

- `site`
- `landing-main`
- `landing-calc`
- `landing-kdm`
- `landing-speed`
- `landing-trust`
- `landing-vedro`
- `telegram`
- `phone`
- `yandex_maps`
- `2gis`
- `avito`
- `vk`
- `max`
- `whatsapp`
- `email`

## Единый формат лида

Каждый входящий лид должен иметь общую структуру:

- `name`
- `phone`
- `source`
- `source_platform`
- `source_channel`
- `source_account`
- `source_listing`
- `source_campaign`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `client_type`
- `concrete_grade`
- `volume`
- `address`
- `delivery_date`
- `urgency`
- `payment_method`
- `comment`
- `calculated_amount`

## Что значат поля

- `source`
  Короткий технический источник для текущего кода. Примеры: `landing-main`, `telegram`, `phone`.

- `source_platform`
  Канальная платформа. Примеры: `site`, `yandex_maps`, `2gis`, `avito`, `vk`, `max`.

- `source_channel`
  Тип входа. Примеры: `form`, `call`, `chat`, `message`.

- `source_account`
  Аккаунт площадки, если их несколько. Особенно важно для `avito`, `vk`, `max`.

- `source_listing`
  Конкретное объявление, карточка компании или объект.

- `source_campaign`
  Кампания, оффер, гипотеза, направление трафика.

## Рекомендуемая воронка amoCRM

Статусы:

1. `Новый лид`
2. `Не дозвонились`
3. `Первичный контакт`
4. `Собираем данные`
5. `Расчет отправлен`
6. `Горячий лид`
7. `Ожидаем подтверждение`
8. `Подтверждено`
9. `Отгружено`
10. `Сделка закрыта`
11. `Отказ / нецелевой`

## Обязательные поля для менеджера

- телефон
- имя
- источник
- платформа
- канал
- адрес
- марка бетона
- объем
- расчетная сумма
- комментарий

## Правила для дублей

- основной ключ дубля: телефон
- если телефон совпадает, лид не должен теряться
- при дубле должен сохраняться новый источник
- если один и тот же клиент пришел из разных каналов, это должно быть видно менеджеру

## Особенности Авито

Для `avito` обязательно хранить:

- `source_platform = avito`
- `source_account`
- `source_listing`
- `source_campaign`

Это нужно, потому что объявления будут регулярно добавляться и могут идти с разных аккаунтов.

## Что уже подготовлено в backend

Backend уже принимает и сохраняет:

- `source_platform`
- `source_channel`
- `source_account`
- `source_listing`
- `source_campaign`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `client_type`

То есть кодовая база уже готова к следующим этапам интеграций.

## Следующий этап

Следующий практический шаг:

1. зафиксировать реальные `ID статусов` в amoCRM под эту воронку
2. определить реальные `custom fields` amoCRM
3. начать подключение `Яндекс Карт` и `2ГИС` к этой схеме

## Что уже готово для боевой amoCRM-настройки

Backend уже умеет подхватывать реальные настройки без переписывания кода:

- `AMOCRM_PIPELINE_STATUSES_JSON`
  JSON-объект для замены статусных ID по именам.

- `AMOCRM_CUSTOM_FIELD_IDS_JSON`
  JSON-объект вида `поле -> field_id`, чтобы лид сразу записывался в кастомные поля amoCRM, а не только в заметки.

- `INTEGRATION_KEYS_JSON`
  JSON-объект вида `интеграция -> секретный ключ` для универсального маршрута `/webhooks/external/{integration}`.

Это значит, что следующий этап можно делать как настройку интеграции, а не как новый рефакторинг backend.

## Что уже готово для внешних площадок

В backend уже есть:

- `GET /api/integrations/schema`
  Каталог поддерживаемых интеграций и их дефолтных source/channel mapping.

- `POST /api/integrations/normalize-preview/{integration}`
  Предпросмотр нормализации сырого payload в лид без создания записи.

- `POST /api/intake/external`
  Единый intake-маршрут для внешних лидов.

- `POST /webhooks/external/{integration}`
  Универсальный webhook для площадок и сервисов, которые будут приходить по одному шаблону.

- `GET /api/sales/workqueue`
  Рабочая очередь отдела продаж: показывает активные лиды, отсортированные по дедлайну и приоритету.

- `POST /api/sales/workqueue/{id}/claim`
  Менеджер берет лид в работу и фиксирует назначение.

- `POST /api/sales/workqueue/{id}/contacted`
  Фиксация первого контакта и перевод лида дальше по воронке.

Это и есть посадочное место под `Яндекс Карты`, `2ГИС`, а затем `Авито`, `ВК`, `MAX`.

## Адаптеры сырых payload

Теперь backend умеет принимать не только заранее нормализованный `lead_data`, но и сырой webhook от канала.

Первый набор адаптеров:

- `telephony`
- `yandex_maps`
- `2gis`
- `avito`
- `vk`
- `whatsapp`
- `telegram`

Задача адаптера:

- вытащить `name`
- вытащить `phone`
- проставить `source_platform`
- проставить `source_channel`
- проставить `source_account`
- проставить `source_listing`
- проставить `source_campaign`
- собрать `comment`

После этого лид идет в общий sales-flow без отдельной архитектуры под каждый сервис.

## Автоматический отдел продаж

Теперь backend умеет автоматически обогащать входящий лид до отправки в amoCRM:

- назначать `sales_priority`
- определять `lead_status`
- выставлять `assigned_manager`
- формировать `next_action`
- выбирать `route_bucket`

Логика стартует именно от `amoCRM`:

`источник -> backend automation -> amoCRM -> отдел продаж`

Это значит, что новые каналы не просто создают лид, а сразу попадают в управляемый sales-поток.

## Playbook и SLA

Теперь автоматизация добавляет к лиду еще 4 рабочих поля:

- `sales_playbook`
- `qualification_script`
- `sla_minutes`
- `contact_deadline_at`

Рекомендуемые сценарии:

- `geo_fast_capture`
  Для `yandex_maps` и `2gis`: быстрый захват лида, SLA 10 минут.

- `marketplace_reactivation`
  Для `avito`: привязка к аккаунту и объявлению, SLA 15 минут.

- `messenger_to_call`
  Для `telegram`, `vk`, `max`, `whatsapp`, `email`: довести до звонка и параметров заказа, SLA 15 минут.

- `hot_call_close`
  Для `phone`: обработка как горячего звонка, SLA 5 минут.

- `standard_followup`
  Для site/form-лидов и остальных каналов: первичная обработка, SLA 30 минут.
