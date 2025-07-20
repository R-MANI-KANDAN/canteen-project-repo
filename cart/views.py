from django.shortcuts import render,get_object_or_404
from .cart import Cart 
#the product model has not been created 
from base.models import Product
from django.http import JsonResponse



# Create your views here.
def cart_summary(request):
    # Get the cart
    cart = Cart(request)
    # Get the products in the cart
    cart_products = cart.get_products()
    product_quantities = cart.get_quantities()

    # Get the total price of the products in the cart
    # total_price = sum(float(product.price) for product in products)

    return render(request, 'cart/cart_summary.html',{"cart_products":cart_products , "product_quantities": product_quantities})

def cart_add(request):
      # Get the cart
      cart = Cart(request)
      # test for POST
      if request.POST.get('action') == 'post':
            # Get stuff
            product_id = int(request.POST.get('product_id'))
            product_quantity = int(request.POST.get('product_quantity'))
            # lookup product in DB
            product = get_object_or_404 (Product, id=product_id)
            # Save to session
            cart.add(product = product , quantity = product_quantity)

            cart_quantity = cart.__len__()

            response = JsonResponse({'quantity' :cart_quantity})
            return response

def cart_delete(request):
    return render(request, 'cart/cart_delete.html')

def cart_update(request):
      # Get the cart
      cart = Cart(request)
      # test for POST
      if request.POST.get('action') == 'post':
            # Get stuff
            product_id = int(request.POST.get('product_id'))
            product_quantity = int(request.POST.get('product_quantity'))

            cart.update(product = product_id, quantity=product_quantity)
            response= JsonResponse({'quantity': product_quantity})
            return response        