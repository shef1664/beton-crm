"""
AI-консультант-продавец «Бетон Экспресс».

Нейросеть ведёт свободный диалог как живой менеджер: объясняет марки и под какой
фундамент какой бетон, считает объём по размерам, консультирует по цене/доставке и
доводит клиента до заявки. Провайдер переключаемый через env AI_PROVIDER.

ВАЖНО (152-ФЗ): персональные данные (телефон, адрес) СЮДА НЕ ПОПАДАЮТ. Их собирает
структурированный поток бота и backend. Агент оперирует только консультацией,
размерами и маркой.

Инструменты (исполняются на backend, без PII):
  1. calc_concrete_volume(shape, ...)  → объём м³   (calculator.calculate_volume)
  2. estimate_price(grade, volume)     → ориентир. цена бетона без доставки
  3. ready_to_order(grade?, volume?)   → сигнал «клиент готов заказать»

chat(history) -> {"reply": str|None, "action": dict|None}
  action может быть {"type": "start_order", "grade": ..., "volume": ...}
  или {"type": "fallback"} если AI недоступен (бот переходит на кнопки).
"""

import json
import logging
import os
from pathlib import Path

from config import settings
from services.calculator import BetonCalculator

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "claude").lower()
AI_MODEL = os.getenv("AI_MODEL", "claude-opus-4-8")
AI_MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "20"))  # последних сообщений

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
        f"\nДоставка: {delivery.get('price_per_km', settings.DELIVERY_PRICE_PER_KM)} ₽/км, "
        f"миксер до {delivery.get('mixer_volume_m3', settings.MIXER_VOLUME)} м³, "
        f"{delivery.get('region', 'Кемерово и область')}. "
        "Точную доставку считает бот по адресу — не называй точную сумму доставки сам."
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
Общаешься с клиентом в Telegram живо, дружелюбно и по делу, на «вы», короткими сообщениями.

Твоя цель: помочь подобрать марку бетона, посчитать объём, сориентировать по цене и
довести до заявки. Ты продавец — мягко веди к заказу, но без навязчивости.

{_load_knowledge()}
{_GRADE_GUIDE}

Правила:
- Объясняй простым языком, задавай по одному уточняющему вопросу (тип конструкции,
  размеры, сроки), чтобы клиент отвечал легко.
- Чтобы посчитать объём — используй инструмент calc_concrete_volume (плита/лента/цилиндр).
- Чтобы назвать ориентировочную цену бетона — используй estimate_price. Всегда говори,
  что это цена бетона без доставки, а доставку посчитает бот по адресу.
- НИКОГДА не спрашивай телефон и точный адрес — это сделает бот кнопками. Если клиент
  готов оформить заказ (или просит рассчитать доставку/цену итог) — вызови ready_to_order
  с известными маркой и объёмом.
- Не выдумывай характеристики и цены — бери из данных выше. Если не знаешь — честно скажи,
  что уточнит менеджер.
- Отвечай на русском. Держи сообщения краткими (2–5 предложений)."""


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
        "name": "ready_to_order",
        "description": "Вызови, когда клиент готов оформить заказ или просит итоговый расчёт с доставкой. Бот переключится на оформление (адрес, дата, оплата, телефон кнопками).",
        "input_schema": {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "description": "Марка, если известна"},
                "volume": {"type": "number", "description": "Объём м³, если известен"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]


def _run_tool(name: str, args: dict, state: dict) -> str:
    """Исполняет инструмент, возвращает текстовый результат для модели."""
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
            return json.dumps({"grade": grade, "volume_m3": volume, "beton_cost_rub": res["beton_cost"],
                               "note": "Это цена бетона БЕЗ доставки. Доставку посчитает бот по адресу."}, ensure_ascii=False)

        if name == "ready_to_order":
            state["action"] = {"type": "start_order", "grade": args.get("grade"), "volume": args.get("volume")}
            return json.dumps({"ok": True, "note": "Переключаю на оформление заказа кнопками."}, ensure_ascii=False)

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

    for _ in range(6):  # предохранитель от бесконечного цикла инструментов
        resp = await client.messages.create(
            model=AI_MODEL,
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
        return {"reply": text or None, "action": state["action"]}

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
