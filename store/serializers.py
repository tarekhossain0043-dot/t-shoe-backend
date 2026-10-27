from .models import Product


def product_brand(product):
    category = (product.category or "").strip()
    text = f"{product.name} {category}".lower()
    if "new balance" in text:
        return "New Balance"
    if "on running" in text or "cloudboom" in text or "cloud " in text:
        return "On Running"
    if "jordan" in text or "aj1" in text or "air jordan" in text:
        return "Air Jordan"
    for brand in ("Nike", "Adidas", "Asics", "Puma", "Reebok", "Converse", "Vans", "Fila", "Skechers"):
        if brand.lower() in text:
            return brand
    return category.split("/")[0].strip() or "Other"


def product_data(p):
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "brand": product_brand(p),
        "price": p.price,
        "image": p.image,
        "description": p.description,
    }
