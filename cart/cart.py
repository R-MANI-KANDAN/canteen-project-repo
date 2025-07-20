from django.conf import settings
from base.models import Product

class Cart():
    def __init__(self, request):
        self.session = request.session
        self.session_key = 'cart'

        cart = self.session.get(self.session_key)

        if not cart:
            cart = self.session[self.session_key] = {}

        self.cart = cart

    def add(self, product , quantity):
        product_id = str(product.id)
        product_quantity = str(quantity)
        # Logic
        if product_id in self.cart :
            pass
        else:
            # self.cart[product_id]={'price': str(product.price)}
            self.cart[product_id] = {"qunatity": product_quantity}
        
        self.session.modified = True

    def __len__(self):
        return len(self.cart)
        

    def get_products(self):
        products_ids = self.cart.keys() 
        products = Product.objects.filter(id__in=products_ids)
        return products
    
    def get_quantities(self):
        quantities = self.cart
        return quantities
    
    def update(self, product, quantity):
        product_id = str(product)
        product_quantity = int(quantity)
        ourcart = self.cart

        # Update only the quantity of the product in the cart
        if product_id in ourcart:
            ourcart[product_id] = product_quantity
            self.session.modified = True
            thing = self.cart
            return thing

           
    


