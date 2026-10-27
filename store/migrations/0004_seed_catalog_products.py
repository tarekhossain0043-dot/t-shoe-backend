from django.db import migrations


BRANDS = [
    "Nike", "Adidas", "Air Jordan", "New Balance", "Puma", "Asics",
    "Reebok", "Converse", "Vans", "On Running", "Fila", "Skechers",
]
MODELS = [
    "Court Classic", "Street Runner", "Retro High", "Everyday Low",
    "Velocity Trainer", "Urban Flex", "Cloud Cushion", "Heritage Canvas",
    "Sport Knit", "Trail Motion",
]
COLORS = [
    "Black/White", "Triple White", "Navy Blue", "Grey/Volt", "Olive",
    "Cream Sand", "Red/Black", "Blue Fog", "Stone Beige", "Forest Green",
]
IMAGES = [
    "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1460353581641-37baddab0fa2?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1495555961986-6d4c1ecb7be3?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1556906781-9a412961c28c?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=700&q=85",
    "https://images.unsplash.com/photo-1520256862855-398228c41684?auto=format&fit=crop&w=700&q=85",
]


def seed_catalog(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    existing_names = set(Product.objects.values_list("name", flat=True))
    existing_count = Product.objects.count()
    target_count = 120
    if existing_count >= target_count:
        return

    candidates = []
    for brand_index, brand in enumerate(BRANDS):
        for model_index, model in enumerate(MODELS):
            color = COLORS[(brand_index * 3 + model_index) % len(COLORS)]
            name = f"{brand} {model} - {color}"
            if name in existing_names:
                continue
            candidates.append({
                "name": name,
                "category": brand,
                "price": 3500 + ((brand_index * 7 + model_index * 3) % 19) * 450,
                "image": IMAGES[(brand_index + model_index) % len(IMAGES)],
                "description": (
                    f"Catalog listing for the {brand} {model.lower()} in {color}. "
                    "Check available sizes and confirm stock with T-SHOE before purchase."
                ),
                "active": True,
            })
    needed = target_count - existing_count
    Product.objects.bulk_create([Product(**item) for item in candidates[:needed]])


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0003_order_structured_delivery_address"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]
