# Description: Context preprocessor to make the cart object globally accessible in templates.
from .cart import Cart

def cart(request):
    return {'cart': Cart(request)}