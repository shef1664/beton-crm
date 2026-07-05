from typing import List

from pydantic import BaseModel


class ServiceCatalogItem(BaseModel):
    name: str
    unit: str
    aliases: List[str]


SERVICE_CATALOG = [
    ServiceCatalogItem(name="Песок строительный", unit="т", aliases=["песок строительный", "песок"]),
    ServiceCatalogItem(name="Песок с доставкой", unit="т", aliases=["песок с доставкой", "песок строительный с доставкой"]),
    ServiceCatalogItem(name="Бетон", unit="м3", aliases=["бетон"]),
    ServiceCatalogItem(name="Аренда техники", unit="усл.", aliases=["аренда техники"]),
    ServiceCatalogItem(name="Услуги автотранспорта", unit="усл.", aliases=["услуги автотранспорта", "автотранспорт"]),
    ServiceCatalogItem(name="Услуги автобетононасоса", unit="усл.", aliases=["услуги автобетононасоса", "автобетононасос"]),
    ServiceCatalogItem(name="Бетон М100", unit="м3", aliases=["бетон м100", "бетоном 100", "м100"]),
    ServiceCatalogItem(name="Бетон М150", unit="м3", aliases=["бетон м150", "бетоном 150", "м150"]),
    ServiceCatalogItem(name="Бетон М200", unit="м3", aliases=["бетон м200", "бетоном 200", "м200"]),
    ServiceCatalogItem(name="Бетон М250", unit="м3", aliases=["бетон м250", "бетоном 250", "м250"]),
    ServiceCatalogItem(name="Бетон М300", unit="м3", aliases=["бетон м300", "бетоном 300", "м300"]),
    ServiceCatalogItem(name="Бетон М350", unit="м3", aliases=["бетон м350", "бетоном 350", "м350"]),
    ServiceCatalogItem(name="Бетон М400", unit="м3", aliases=["бетон м400", "бетоном 400", "м400"]),
]

