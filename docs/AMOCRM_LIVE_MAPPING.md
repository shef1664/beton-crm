# amoCRM Live Mapping

Актуальная живая конфигурация, автоматически снятая из рабочего аккаунта `shef1664.amocrm.ru`.

## Аккаунт

- `account_id`: `33010006`
- `pipeline_id`: `10818570`
- `pipeline_name`: `Продажи бетона`

## Статусы воронки

- `unprocessed`: `85162966`
- `new`: `85162970`
- `data_collection`: `85162974`
- `calculation`: `85162978`
- `hot_lead`: `85162982`
- `confirmed`: `85162986`
- `won`: `142`
- `lost`: `143`

## Подключенные lead custom fields

- `source_platform`: `1502999`
- `source_channel`: `1503027`
- `source_account`: `1503029`
- `source_listing`: `1503031`
- `source_campaign`: `1503033`
- `client_type`: `1503035`
- `concrete_grade`: `1503037`
- `volume`: `1503039`
- `address`: `1503041`
- `delivery_date`: `1503043`
- `urgency`: `1503045`
- `payment_method`: `1503047`
- `comment`: `1503049`
- `calculated_amount`: `1503051`
- `distance`: `1503053`
- `sales_priority`: `1503055`
- `assigned_manager`: `1503057`
- `lead_status`: `1503059`
- `next_action`: `1503061`
- `route_bucket`: `1503063`
- `sales_playbook`: `1503065`
- `qualification_script`: `1503067`
- `sla_minutes`: `1503069`
- `contact_deadline_at`: `1503071`
- `utm_source`: `1494501`
- `utm_medium`: `1494497`
- `utm_campaign`: `1494499`

## Примечание

Токены и другие секреты сюда не выносятся. Рабочие значения уже записаны в `backend/.env`, а backend читает их автоматически через:

- `AMOCRM_PIPELINE_STATUSES_JSON`
- `AMOCRM_CUSTOM_FIELD_IDS_JSON`
