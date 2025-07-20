from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image
import os
import datetime


class Category(models.Model):
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name
    class Meta :
        verbose_name_plural = 'Categories'


class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(default = ' ',decimal_places = 2 ,max_digits=7)
    category = models.ForeignKey(Category , on_delete = models.CASCADE)
    image = models.ImageField(upload_to = 'uploads/product/')
    code_no = models.IntegerField(default=' ')
    quantity = models.PositiveIntegerField(default=1)

   
    # is the food is available 
    is_sale = models.BooleanField(default=True)
    sub_category = models.CharField(max_length=100, blank=True, null=True)  
    def __str__(self):

        return self.name
    



class Landing_img(models.Model):
    image = models.ImageField(upload_to='uploads/landing/')
    title = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.title 




class Customer(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=10)  # Changed to CharField
    email = models.EmailField(max_length=100)
    password = models.CharField(max_length=100)  # Fixed from PasswordField to CharField

    def __str__(self):
        return self.first_name


class Order(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    
    quantity = models.IntegerField(default=1)  
    
    order_id = models.AutoField(primary_key=True)  # Auto-generated order number
    student_id = models.CharField(max_length=20)  # Use CharField to support alphanumeric reg. no.

    status = models.BooleanField(default=False)
    date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return self.product







class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        default='profile_pics/default.jpg',  # Fixed default filename
        blank=True,
        null=True
    )
    phone_number = models.CharField(max_length=20, blank=True)
    
    def remove_profile_picture(self):
        """Remove the current profile picture and reset to default"""
        if self.profile_picture and self.profile_picture.name != 'profile_pics/default.jpg':
            # Delete the file from storage
            if os.path.isfile(self.profile_picture.path):
                os.remove(self.profile_picture.path)
            # Set to default
            self.profile_picture = 'profile_pics/default.jpg'
            self.save()
            
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def save(self, *args, **kwargs):
        # Delete old file when updating
        try:
            old = Profile.objects.get(id=self.id)
            if old.profile_picture and old.profile_picture != self.profile_picture:
                if os.path.isfile(old.profile_picture.path):
                    os.remove(old.profile_picture.path)
        except Profile.DoesNotExist:
            pass
        
        super().save(*args, **kwargs)
        
        # Resize image if exists
        if self.profile_picture:
            try:
                img = Image.open(self.profile_picture.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.profile_picture.path)
            except Exception as e:
                # Handle image processing errors gracefully
                print(f"Error processing image: {e}")

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()





    