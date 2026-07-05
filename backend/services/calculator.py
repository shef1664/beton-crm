"""Калькулятор бетона"""
import math

from config import settings

class BetonCalculator:
    @staticmethod
    def calculate(grade: str, volume: float, distance: float = 0) -> float:
        """Расчёт стоимости бетона и доставки.

        Доставка = (км × ставка_за_км + база_за_подачу) × объём_к_оплате,
        объём_к_оплате = max(MIN_BILLABLE_VOLUME, ceil(volume)).
        """
        price_per_m3 = settings.BETON_PRICES.get(grade)
        if not price_per_m3:
            raise ValueError(f"Неизвестная марка бетона: {grade}")

        beton_cost = price_per_m3 * volume

        billable_volume = max(settings.MIN_BILLABLE_VOLUME, math.ceil(volume))
        delivery_per_m3 = distance * settings.DELIVERY_PER_KM_PER_M3 + settings.DELIVERY_BASE_PER_M3
        delivery_cost = delivery_per_m3 * billable_volume
        total = beton_cost + delivery_cost

        return {
            "concrete_grade": grade,
            "volume": volume,
            "billable_volume": billable_volume,
            "price_per_m3": price_per_m3,
            "beton_cost": beton_cost,
            "distance": distance,
            "delivery_per_m3": round(delivery_per_m3, 2),
            "delivery_cost": round(delivery_cost, 2),
            "total": round(total, 2),
            "mixers_needed": max(1, math.ceil(volume / settings.MIXER_VOLUME)),
        }
    
    @staticmethod
    def calculate_volume(form_type: str, **kwargs) -> float:
        """Расчёт объёма бетона"""
        if form_type == "slab":  # Плита
            return kwargs["length"] * kwargs["width"] * kwargs["height"]
        
        elif form_type == "tape":  # Ленточный фундамент
            return kwargs["perimeter"] * kwargs["width"] * kwargs["height"]
        
        elif form_type == "cylinder":  # Цилиндр
            import math
            return math.pi * (kwargs["radius"] ** 2) * kwargs["height"]
        
        else:
            raise ValueError(f"Неизвестный тип: {form_type}")
    
    @staticmethod
    def calculate_cylinder_area(radius: float, height: float) -> float:
        """Расчёт площади цилиндра: S = 2πrh"""
        import math
        return 2 * math.pi * radius * height
