"""Concrete pricing calculator."""

import math

from config import settings


class BetonCalculator:
    @staticmethod
    def calculate(grade: str, volume: float, distance: float = 0) -> dict:
        """Calculate concrete and delivery costs."""
        price_per_m3 = settings.BETON_PRICES.get(grade)
        if not price_per_m3:
            raise ValueError(f"Unknown concrete grade: {grade}")

        beton_cost = price_per_m3 * volume

        # Delivery formula:
        # (distance * 35 + 650) gives delivery price per m3.
        # Billing volume is never lower than 6 m3.
        delivery_price_per_m3 = (distance * settings.DELIVERY_RATE_PER_KM) + settings.DELIVERY_BASE_FEE
        delivery_charged_volume = max(settings.DELIVERY_MIN_CHARGED_VOLUME, math.ceil(volume))
        delivery_cost = delivery_price_per_m3 * delivery_charged_volume
        total = beton_cost + delivery_cost

        return {
            "concrete_grade": grade,
            "volume": volume,
            "price_per_m3": price_per_m3,
            "beton_cost": beton_cost,
            "distance": distance,
            "delivery_price_per_m3": round(delivery_price_per_m3, 2),
            "delivery_charged_volume": delivery_charged_volume,
            "delivery_cost": round(delivery_cost, 2),
            "total": round(total, 2),
            "mixers_needed": max(1, math.ceil(volume / settings.MIXER_VOLUME)),
        }

    @staticmethod
    def calculate_volume(form_type: str, **kwargs) -> float:
        """Calculate concrete volume by form type."""
        if form_type == "slab":
            return kwargs["length"] * kwargs["width"] * kwargs["height"]

        if form_type == "tape":
            return kwargs["perimeter"] * kwargs["width"] * kwargs["height"]

        if form_type == "cylinder":
            return math.pi * (kwargs["radius"] ** 2) * kwargs["height"]

        raise ValueError(f"Unknown form type: {form_type}")

    @staticmethod
    def calculate_cylinder_area(radius: float, height: float) -> float:
        """Calculate cylinder area: S = 2prh."""
        return 2 * math.pi * radius * height
