from .models import Product
def product_data(p):
 return {"id":p.id,"name":p.name,"category":p.category,"price":p.price,"image":p.image,"description":p.description}
