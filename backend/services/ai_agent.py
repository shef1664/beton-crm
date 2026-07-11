"""
AI-консультант-продавец «Бетон Экспресс».

Нейросеть ведёт свободный диалог как живой менеджер: объясняет марки и под какой
фундамент какой бетон, считает объём по размерам, консультирует по цене/доставке и
доводит клиента до заявки. Провайдер переключаемый через env AI_PROVIDER.

Нейросеть ведёт ВЕСЬ клиентский диалог: подбор марки, объём, адрес, полная цена с
доставкой, дата/оплата, и оформление заказа. ТЕЛЕФОН через нейросеть не идёт — его
собирает бот кнопкой «отправить контакт» (по действию request_phone). Адрес нужен
для расчёта доставки и передаётся агенту.

Инструменты (исполняются на backend):
  1. calc_concrete_volume(shape, ...)          → объём м³
  2. estimate_price(grade, volume)             → цена бетона без доставки
  3. get_delivery_quote(grade, volume, address)→ полная цена (бетон + доставка по зоне)
  4. request_phone(grade, volume, address, ...) → запросить ручной ввод телефона и оформить
  5. call_human(reason)                        → живой менеджер

chat(history) -> {"reply": str|None, "action": dict|None}
  action: {"type": "request_phone", "order": {...}} — бот просит вручную ввести телефон;
          {"type": "call_human", ...} — передача менеджеру;
          {"type": "fallback"} — AI недоступен (бот на кнопки).
"""

import json
import logging
import math
import os
from pathlib import Path

from config import settings
from services import geo
from services.calculator import BetonCalculator

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "claude").lower()
AI_MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "20"))  # последних сообщений

# Роутинг моделей по сложности запроса:
#   • сложное (подбор марки под фундамент, расчёты, нюансы) → Fable 5 (максимум качества);
#   • среднее (обычный диалог продажи)                      → Opus 4.8;
#   • лёгкое (приветствие, «да/нет», спасибо, короткое)     → Haiku 4.5 (быстро/дёшево).
# Если задан AI_MODEL — он форсит одну модель для всех уровней (обратная совместимость).
AI_MODEL = os.getenv("AI_MODEL", "").strip()
AI_MODEL_LIGHT = os.getenv("AI_MODEL_LIGHT", "claude-haiku-4-5-20251001")
AI_MODEL_MEDIUM = os.getenv("AI_MODEL_MEDIUM", "claude-opus-4-8")
AI_MODEL_COMPLEX = os.getenv("AI_MODEL_COMPLEX", "claude-fable-5")

# Сигналы «сложного» запроса — техническая консультация по бетону/конструкции.
_COMPLEX_MARKERS = (
    "фундамент", "марк", "какой бетон", "какую марку", "перекрыт", "нагруз", "толщин",
    "арматур", "морозостойк", "водонепрониц", "пропорц", "состав", "класс", "b15", "b20",
    "b22", "b25", "b30", "монолит", "лент", "плит", "сваи", "ростверк", "стяжк", "отмостк",
    "почему", "чем отлич", "что лучше", "посчита", "рассчита", "объ[её]м", "куб",
)
# Сигналы «лёгкого» запроса — короткие реплики без консультации.
_LIGHT_MARKERS = (
    "спасибо", "ок", "хорошо", "да", "нет", "привет", "здрав", "добрый", "понял",
    "давай", "ясно", "угу", "ок.", "спс",
)

_HANDOFF_REPLY_MARKERS = (
    "не могу помочь",
    "не смогу помочь",
    "не помогу",
    "не знаю",
    "не уверен",
    "не уверена",
    "не моя тема",
    "только по бетону",
    "уточнит менеджер",
    "уточнить у менеджера",
)


def _reply_requires_handoff(reply: str) -> bool:
    """Страховка: отказ или неуверенность AI всегда передаются менеджеру."""
    normalized = (reply or "").strip().lower()
    return any(marker in normalized for marker in _HANDOFF_REPLY_MARKERS)


def _pick_model(messages: list) -> str:
    """Выбрать модель по сложности последней реплики клиента."""
    if AI_MODEL:
        return AI_MODEL
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            last = m["content"].strip().lower()
            break
    if not last:
        return AI_MODEL_MEDIUM

    has_digit = any(ch.isdigit() for ch in last)
    complex_hit = any(mk in last for mk in _COMPLEX_MARKERS)
    many_questions = last.count("?") >= 2
    # размеры вида «10х8», «0.4 на 0.6» — почти всегда расчёт объёма
    dims = ("х" in last and has_digit) or (" на " in last and has_digit)

    if complex_hit or many_questions or dims or len(last) > 200:
        return AI_MODEL_COMPLEX
    # короткая реплика без цифр и техсигналов → лёгкая модель
    words = last.split()
    if len(last) <= 30 and not has_digit and (
        len(words) <= 4 or any(last.startswith(mk) for mk in _LIGHT_MARKERS)
    ):
        return AI_MODEL_LIGHT
    return AI_MODEL_MEDIUM

_calc = BetonCalculator()
_LANDING_CONFIG = Path(__file__).resolve().parent.parent / "data" / "landing_config.json"


# ── База знаний для system-промпта ──────────────────────────────────────────

def _load_knowledge() -> str:
    """Собирает базу знаний из landing_config.json (единый источник цен)."""
    lines = []
    try:
        cfg = json.loads(_LANDING_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("landing_config.json недоступен: %s", exc)
        cfg = {}

    items = (cfg.get("pricing") or {}).get("items") or []
    if items:
        lines.append("Марки бетона, цена (₽/м³) и назначение:")
        for it in items:
            lines.append(f"  • {it['grade']} — {it['price']} ₽/м³ — {it.get('description','')}")
    else:
        lines.append("Цены (₽/м³): " + ", ".join(f"{g}={p}" for g, p in settings.BETON_PRICES.items()))

    delivery = cfg.get("delivery") or {}
    lines.append(
        f"\nДоставка платная, зависит от адреса и объёма (миксер до "
        f"{delivery.get('mixer_volume_m3', settings.MIXER_VOLUME):g} м³, "
        f"{delivery.get('region', 'Кемерово и область')}). Средний чек по городу ≈ 6–7 тыс ₽. "
        "Точную сумму доставки считает бот по адресу — сам её не называй, дай только порядок."
    )
    faq = cfg.get("faq") or []
    if faq:
        lines.append("\nЧастые вопросы:")
        for q in faq:
            lines.append(f"  • {q.get('question','')} — {q.get('answer','')}")
    return "\n".join(lines)


_GRADE_GUIDE = """
Соответствие марки и конструкции (используй при подборе):
  • М100 — подготовка под фундамент, подбетонка, подушки.
  • М150 — стяжки, полы, дорожки, нетяжёлые основания.
  • М200 — ленточные и плитные фундаменты частных домов, отмостки, лестницы.
  • М250 — монолитные фундаменты, плиты перекрытия небольших нагрузок.
  • М300 — САМАЯ ПОПУЛЯРНАЯ: фундаменты, монолит, перекрытия, площадки. Универсал.
  • М350 — колонны, несущие стены, перекрытия с нагрузкой, монолитные каркасы.
  • М400 — мосты, бассейны, гидротехника, тяжелонагруженные конструкции.
  • М450 — особо ответственные и специальные конструкции.
Нюансы: для фундамента частного дома обычно М300 (М200 — если лёгкий дом/грунт хороший).
Морозостойкость/водонепроницаемость выше у старших марок. Зимой нужен прогрев/противоморозные добавки.
"""

SYSTEM_PROMPT = f"""Ты — Максим, менеджер по продажам компании «Бетон Экспресс» (Кемерово).
Общаешься с клиентом в Telegram или MAX живо, дружелюбно и по делу, на «вы», короткими сообщениями.

Твоя цель: помочь подобрать марку бетона, посчитать объём, сориентировать по цене и
довести до заявки. Ты продавец — мягко веди к заказу, но без навязчивости.

{_load_knowledge()}
{_GRADE_GUIDE}

Правила:
Ты ведёшь весь диалог сам, по шагам, задавая по одному простому вопросу:
1. Что заливаем и размеры → при необходимости посчитай объём инструментом
   calc_concrete_volume (плита/лента/цилиндр). Подскажи марку под задачу.
2. Спроси адрес доставки (город, район/населённый пункт, улица) — он нужен для расчёта.
3. Назови полную стоимость инструментом get_delivery_quote (бетон + доставка по зоне).
   Если зона вне тарифов — честно скажи, что доставку уточнит менеджер.
4. Уточни дату доставки и способ оплаты.
5. Когда собрал марку, объём и адрес (и по возможности дату/оплату) и клиент согласен —
   вызови request_phone со всеми собранными данными. Бот сам попросит клиента вручную
   ввести номер телефона; номер через нейросеть не передаётся.

Правила:
- Работай только по теме бетона, расчёта, доставки, оплаты, заказа и контактов компании.
- Не уходи в длинные рассуждения, посторонние темы или догадки. Ответ — 2–4 коротких
  предложения и не более одного вопроса за раз.
- Если не понял запрос, не уверен в ответе, не хватает данных из базы знаний, инструмент
  вернул ошибку или вопрос нестандартный — СРАЗУ вызови call_human. Не пытайся угадывать,
  повторно переспрашивать или импровизировать.
- Спрашивай адрес — можно. Телефон через диалог НЕ собирай: вызови request_phone, после
  чего бот отдельно попросит клиента ввести номер вручную.
- Не выдумывай цены/характеристики — бери из данных выше и из инструментов. Не знаешь —
  вызови call_human.
- Живого менеджера (недоволен, торг, юрлицо, спецусловия, рекламация, вопрос вне темы) —
  вызови call_human.
- Отвечай на русском, кратко (2–4 предложения), дружелюбно, веди к заказу без навязчивости."""


# ── Инструменты (без PII) ───────────────────────────────────────────────────

TOOLS = [
    {
        "name": "calc_concrete_volume",
        "description": "Рассчитать объём бетона (м³) по форме конструкции и размерам в метрах.",
        "input_schema": {
            "type": "object",
            "properties": {
                "shape": {
                    "type": "string",
                    "enum": ["slab", "tape", "cylinder"],
                    "description": "slab=плита (length×width×height), tape=лента/ленточный фундамент (perimeter×width×height), cylinder=цилиндр/столб (radius,height)",
                },
                "length": {"type": "number", "description": "Длина, м (для slab)"},
                "width": {"type": "number", "description": "Ширина, м (slab/tape)"},
                "height": {"type": "number", "description": "Высота/толщина, м"},
                "perimeter": {"type": "number", "description": "Периметр ленты, м (для tape)"},
                "radius": {"type": "number", "description": "Радиус, м (для cylinder)"},
            },
            "required": ["shape"],
            "additionalProperties": False,
        },
    },
    {
        "name": "estimate_price",
        "description": "Ориентировочная цена БЕТОНА (без доставки) по марке и объёму. Доставку считает бот отдельно по адресу.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "description": "Марка, напр. М300"},
                "volume": {"type": "number", "description": "Объём, м³"},
            },
            "required": ["grade", "volume"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_delivery_quote",
        "description": "Полная стоимость: бетон + доставка по адресу (зона). Вызови после того, как узнал марку, объём и адрес. Вернёт цену бетона, доставку (или «уточнит менеджер»), итог.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "description": "Марка, напр. М300"},
                "volume": {"type": "number", "description": "Объём, м³"},
                "address": {"type": "string", "description": "Адрес доставки (город/район/улица)"},
            },
            "required": ["grade", "volume", "address"],
            "additionalProperties": False,
        },
    },
    {
        "name": "request_phone",
        "description": "Оформить заказ: попросить клиента вручную ввести телефон. Вызывай, когда собрал марку, объём и адрес (и по возможности дату/оплату) и клиент согласен заказать. Телефон соберёт бот отдельно.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "description": "Марка"},
                "volume": {"type": "number", "description": "Объём, м³"},
                "address": {"type": "string", "description": "Адрес доставки"},
                "delivery_date": {"type": "string", "description": "Когда нужна доставка (если уточнили)"},
                "payment_method": {"type": "string", "description": "Способ оплаты (если уточнили)"},
            },
            "required": ["grade", "volume", "address"],
            "additionalProperties": False,
        },
    },
    {
        "name": "call_human",
        "description": "Вызови, когда клиент просит живого менеджера/оператора, недоволен, торгуется по цене, задаёт вопрос вне твоей компетенции (нестандартный объект, юрлицо, спецусловия, рекламация). Бот подключит живого сотрудника отдела продаж.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Кратко причина передачи менеджеру"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]


def _run_tool(name: str, args: dict, state: dict) -> str:
    """Исполняет инструмент, возвращает текстовый результат для модели.

    По ходу диалога накапливаем заказ (state["order"]) и расчёт (state["quote"]),
    чтобы марка/объём/адрес/сумма гарантированно попали в заявку — даже если
    модель вызовет request_phone без части аргументов.
    """
    order = state.setdefault("order", {})
    try:
        if name == "calc_concrete_volume":
            shape = args.get("shape")
            if shape == "slab":
                vol = _calc.calculate_volume("slab", length=args["length"], width=args["width"], height=args["height"])
            elif shape == "tape":
                vol = _calc.calculate_volume("tape", perimeter=args["perimeter"], width=args["width"], height=args["height"])
            elif shape == "cylinder":
                vol = _calc.calculate_volume("cylinder", radius=args["radius"], height=args["height"])
            else:
                return "Ошибка: неизвестная форма."
            vol = round(vol, 2)
            return json.dumps({"volume_m3": vol,
                               "note": "К оплате обычно округляют вверх; один миксер до 7 м³."},
                              ensure_ascii=False)

        if name == "estimate_price":
            grade = args["grade"]
            volume = float(args["volume"])
            if grade not in settings.BETON_PRICES:
                return f"Ошибка: неизвестная марка. Доступны: {', '.join(settings.BETON_PRICES)}"
            res = _calc.calculate(grade, volume, 0)
            order["grade"] = grade
            order["volume"] = volume
            return json.dumps({"grade": grade, "volume_m3": volume, "beton_cost_rub": res["beton_cost"],
                               "note": "Это цена бетона БЕЗ доставки. Доставку посчитает бот по адресу."}, ensure_ascii=False)

        if name == "get_delivery_quote":
            grade = args["grade"]
            volume = float(args["volume"])
            if grade not in settings.BETON_PRICES:
                return f"Ошибка: неизвестная марка. Доступны: {', '.join(settings.BETON_PRICES)}"
            beton = round(settings.BETON_PRICES[grade] * volume, 2)
            mixers = max(1, math.ceil(volume / settings.MIXER_VOLUME))
            zone = geo.match_zone(args["address"])
            order["grade"] = grade
            order["volume"] = volume
            order["address"] = args["address"]
            if zone and zone.get("price_min") is not None:
                dmin, dmax = zone["price_min"] * mixers, zone["price_max"] * mixers
                state["quote"] = {"zone": zone["name"], "beton_cost": beton, "mixers": mixers,
                                  "delivery_min": dmin, "delivery_max": dmax,
                                  "total_min": beton + dmin, "total_max": beton + dmax,
                                  "distance_km": zone.get("km"), "needs_manager": False}
                return json.dumps({"zone": zone["name"], "beton_cost_rub": beton, "mixers": mixers,
                                   "delivery_rub": [dmin, dmax], "total_rub": [beton + dmin, beton + dmax],
                                   "note": "Итог ориентировочный, финал подтвердит менеджер."}, ensure_ascii=False)
            state["quote"] = {"zone": (zone or {}).get("name"), "beton_cost": beton, "mixers": mixers,
                              "delivery_min": None, "delivery_max": None,
                              "total_min": None, "total_max": None,
                              "distance_km": (zone or {}).get("km"), "needs_manager": True}
            return json.dumps({"zone": (zone or {}).get("name"), "beton_cost_rub": beton, "mixers": mixers,
                               "delivery_rub": None,
                               "note": "Адрес вне тарифных зон — стоимость доставки уточнит менеджер."}, ensure_ascii=False)

        if name == "request_phone":
            # Явные аргументы имеют приоритет, недостающие берём из накопленного заказа
            for key in ("grade", "volume", "address", "delivery_date", "payment_method"):
                val = args.get(key)
                if val is not None:
                    order[key] = val
            state["action"] = {"type": "request_phone", "order": dict(order), "quote": state.get("quote")}
            return json.dumps({"ok": True, "note": "Бот попросит клиента вручную ввести телефон."}, ensure_ascii=False)

        if name == "call_human":
            state["action"] = {"type": "call_human", "reason": args.get("reason", "")}
            return json.dumps({"ok": True, "note": "Подключаю живого менеджера отдела продаж."}, ensure_ascii=False)

        return "Ошибка: неизвестный инструмент."
    except Exception as exc:
        logger.warning("tool %s failed: %s", name, exc)
        return f"Ошибка при расчёте: {exc}"


# ── Провайдеры ──────────────────────────────────────────────────────────────

async def _chat_claude(history: list) -> dict:
    """Агентный цикл на Claude (официальный Anthropic SDK)."""
    import anthropic  # локальный импорт: зависимость нужна только при AI_PROVIDER=claude

    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY не задан — AI недоступен")
        return {"reply": None, "action": {"type": "fallback"}}

    client = anthropic.AsyncAnthropic()
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-AI_MAX_HISTORY:]]
    state = {"action": None}
    model = _pick_model(messages)  # модель по сложности запроса (один раз на ход диалога)
    logger.info("AI model: %s", model)

    for _ in range(6):  # предохранитель от бесконечного цикла инструментов
        resp = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            output_config={"effort": "low"},
            messages=messages,
        )
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = _run_tool(block.name, block.input or {}, state)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            messages.append({"role": "user", "content": results})
            continue
        # финальный ответ
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        action = state["action"]
        if not action and _reply_requires_handoff(text):
            action = {
                "type": "call_human",
                "reason": "Нейросеть не смогла уверенно ответить клиенту",
            }
        return {"reply": text or None, "action": action}

    return {"reply": "Давайте оформим заявку — так менеджер быстро всё посчитает.",
            "action": state["action"] or {"type": "start_order"}}


async def _chat_gigachat(history: list) -> dict:
    """Заглушка под GigaChat/Сбер (подключим позже через env AI_PROVIDER=gigachat)."""
    logger.warning("GigaChat провайдер ещё не реализован")
    return {"reply": None, "action": {"type": "fallback"}}


async def chat(history: list) -> dict:
    """
    Главная точка входа. history — список {role: 'user'|'assistant', content: str}
    БЕЗ персональных данных. Возвращает {reply, action}. Ошибки → fallback на кнопки.
    """
    try:
        if AI_PROVIDER == "gigachat":
            return await _chat_gigachat(history)
        return await _chat_claude(history)
    except Exception as exc:
        logger.error("AI chat failed: %s", exc)
        return {"reply": None, "action": {"type": "fallback"}}
