from django.core.management.base import BaseCommand
from store.models import Product
ITEMS=[
("Air Runner Pro","Running Shoes",2890,"https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=700&q=85","Lightweight performance shoes for everyday training."),
("Street Classic","Sneakers",2390,"https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=700&q=85","A clean classic sneaker for daily wear."),
("Cloud Pace","Running Shoes",3190,"https://images.unsplash.com/photo-1495555961986-6d4c1ecb7be3?auto=format&fit=crop&w=700&q=85","Responsive cushioning and a breathable upper."),
("Retro Court","Casual Shoes",2590,"https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&w=700&q=85","Retro court-inspired comfort."),
("Urban Flex","Casual Shoes",1990,"https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=700&q=85","Flexible everyday footwear."),
("Velocity Sport","Running Shoes",3490,"https://images.unsplash.com/photo-1460353581641-37baddab0fa2?auto=format&fit=crop&w=700&q=85","Built for pace, comfort and movement."),
("Everyday Canvas","Sneakers",1790,"https://images.unsplash.com/photo-1520256862855-398228c41684?auto=format&fit=crop&w=700&q=85","Easy-to-style canvas shoes."),
("Bold Track","Running Shoes",2990,"https://images.unsplash.com/photo-1556906781-9a412961c28c?auto=format&fit=crop&w=700&q=85","Bold styling with all-day comfort.")]
class Command(BaseCommand):
 help="Create demo T-Shoe products"
 def handle(self,*args,**kwargs):
  for name,category,price,image,description in ITEMS:
   Product.objects.update_or_create(name=name,defaults={"category":category,"price":price,"image":image,"description":description,"stock_quantity":8,"active":True})
  self.stdout.write(self.style.SUCCESS("Demo products created/updated with 8 units each. Use only for development/testing."))
