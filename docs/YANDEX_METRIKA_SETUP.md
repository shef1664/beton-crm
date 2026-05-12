# Яндекс.Метрика — настройка для бетон42.рф

## Что даст подключение Метрики

1. **Аналитика трафика** — откуда приходят посетители, какие страницы смотрят
2. **Цели и конверсии** — сколько кликают форму, сколько отправляют, сколько звонят
3. **Ретаргетинг для Яндекс.Директ** — догонять тех кто открыл сайт но не оставил заявку
4. **Карта кликов, скроллов, вебвизор** — посмотреть «глазами клиента» куда жмут на лендинге
5. **Атрибуция** — какой канал реально приносит деньги (не клики, а сделки в AmoCRM)

---

## Шаги активации (твои действия)

### 1. Создать счётчик

1. Открыть https://metrika.yandex.ru/ (войти своим Яндекс-аккаунтом)
2. **Добавить счётчик**
3. Имя: `Бетон42.рф`
4. Адрес сайта: `xn--42-9kcq4bf1a.xn--p1ai` (punycode) или `бетон42.рф`
5. Часовой пояс: **Asia/Krasnoyarsk (UTC+7)** — Кемерово
6. Опции: **включить** «Вебвизор», «Карты», «Аналитика форм»
7. Сохранить → получишь **8-значный Counter ID** (пример: `12345678`)

### 2. Прислать мне Counter ID

Просто число (8 цифр). Я:
- Вставлю снippet в `landing/index.html`
- Закоммичу + смержу
- Render передеплоит за 2 мин
- Метрика начнёт считать

### 3. Создать цели (после первого деплоя)

В Метрике → **Настройка** → **Цели** → **Добавить цель**:

**Цель A: «Отправка формы»** — type=`JavaScript-событие`, ID=`lead_submitted`
**Цель B: «Клик на телефон»** — type=`URL`, условие `Содержит "tel:"`
**Цель C: «Открыт калькулятор»** — type=`JavaScript-событие`, ID=`calc_opened`
**Цель D: «Скролл 75%»** — type=`Глубина просмотра`, значение `75`

После создания целей — пришли мне их ID, я добавлю вызовы `ym(<counter>, 'reachGoal', '<goal_id>')` в нужные места лендинга (форма, телефон, калькулятор).

---

## Технически: как я подключу

### Snippet в `<head>` лендинга

```html
<!-- Yandex.Metrika counter -->
<script type="text/javascript" >
   (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
   m[i].l=1*new Date();
   for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
   k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
   (window, document, "script", "https://mc.yandex.ru/metrika/tag.js?id=COUNTER_ID", "ym");

   ym(COUNTER_ID, "init", {
        clickmap:true,
        trackLinks:true,
        accurateTrackBounce:true,
        webvisor:true,
        ecommerce:"dataLayer"
   });
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/COUNTER_ID" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
```

`COUNTER_ID` я заменю на твой реальный 8-значный ID.

### Вызовы целей (после первого деплоя + создания целей)

В `leadSubmit()` в landing/index.html, после успешного ответа от backend:
```js
if (typeof ym !== 'undefined') {
  ym(COUNTER_ID, 'reachGoal', 'lead_submitted', {
    grade: payload.concrete_grade,
    volume: payload.volume,
    amount: calculated_total
  });
}
```

В обработчике клика на `tel:` ссылку (телефоны в шапке):
```js
document.querySelectorAll('a[href^="tel:"]').forEach(a => {
  a.addEventListener('click', () => {
    if (typeof ym !== 'undefined') ym(COUNTER_ID, 'reachGoal', 'click_to_call');
  });
});
```

---

## Backend интеграция с Метрика API (фаза 2)

Когда счётчик начнёт собирать данные, можно подключить **сквозную аналитику**:

1. **Метрика API → AmoCRM** — для каждого лида в AmoCRM записываем какой visit_id привёл к заявке. Тогда видно «такой-то клик из Директа стал сделкой».
2. **Метрика Logs API** — выгружать сырые хиты в backend, делать собственные срезы (LTV по UTM-кампаниям, и т.д.).

Это уже есть в скилле `ru-sales-stack` → `references/yandex-metrika.md`. Активирую когда подключим Директ.

---

## Что готово ждать тебя

В коде уже есть UTM-маппинг: backend принимает `utm_source`, `utm_medium`, `utm_campaign` от формы и записывает в кастомные поля AmoCRM. Это значит **как только запустим Директ с UTM-разметкой, видишь в воронке какая кампания принесла какие сделки** — без отдельной интеграции.

Просто пришли мне 8-значный Counter ID — я подключу за 1 коммит.
