#!/usr/bin/env python3
"""
Быстрый тест Марии.
Запуск: python3 test-maria.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from maria_integration import MariaBotHandler

def main():
    print("🎤 ТЕСТ МАРИИ\n")
    print("=" * 60)

    handler = MariaBotHandler()

    # Тестовый диалог
    test_conversation = [
        "Привет, сколько стоит бетон М300?",
        "Нужно 5 кубов",
        "В Кемерово, Октябрьский район",
        "А если мне нужно через час?",
        "Хорошо, готов заказать",
    ]

    for i, client_msg in enumerate(test_conversation, 1):
        print(f"\n📞 Клиент (ход {i}): {client_msg}")

        try:
            result = handler.process_client_message(client_msg)

            print(f"🎤 Мария: {result['text']}")

            if result['transfer_needed']:
                print(f"\n⚠️  ПЕРЕДАЧА НА МЕНЕДЖЕРА ({result['transfer_phone']})")
                break
            else:
                print(f"✅ Продолжает диалог")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            break

    print("\n" + "=" * 60)
    print("✅ Тест завершён\n")


if __name__ == "__main__":
    main()
