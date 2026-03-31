from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from .manager import *
from ckeditor_uploader.fields import RichTextUploadingField
from django.urls import reverse
import datetime
from django.utils.text import slugify
from cities_light.models import City, Country
import uuid
import string
import random
from cloudinary.models import CloudinaryField


class myuser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_seller = models.BooleanField(default=False)
    is_customer = models.BooleanField(default= False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return f'{self.first_name} {self.last_name}'





class Agreement(models.Model):
    user = models.OneToOneField(myuser, on_delete= models.CASCADE)
    created_date = models.DateTimeField(auto_now_add = True)




Gender = [
    ('Male', 'Male'),
    ('Female', 'Female'),
]

class CustomerProfile(models.Model):
    # Link to your custom user model
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    # Profile specific fields
    phone = models.CharField(max_length=15, blank=True, null=True)
    phone_secondary = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Profile for {self.user.email}"


def generate_registration_number():
    # Example format: DB-XXXX-XXXX (Diaspora Black)
    prefix = "DB"
    chars = string.ascii_uppercase + string.digits
    unique_id = ''.join(random.choices(chars, k=8))
    return f"{prefix}-{unique_id[:4]}-{unique_id[4:]}"

class ShopProfile(models.Model):
    BusinessModel =[
        ('Individual', 'Individual'),
        ('Company', 'Company'),
      
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_profile')
    shop_name = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='shops/logos/', null=True, blank=True)
    business_type = models.CharField(max_length= 100, choices= BusinessModel, null=False,blank=False, help_text='Please select if you are an individual or Business Entity/Company')
    phone_number = models.CharField(max_length=20, null =False, blank = False)
    business_address = models.TextField()
    bank_name = models.CharField(max_length = 100)
    account_number = models.CharField(max_length = 11,null=True)
    sort_code =  models.CharField(max_length = 11,null=True,blank = True)
    registration_number = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False, 
        default=generate_registration_number
    )
    country = models.ForeignKey(Country, on_delete=models.CASCADE,null = True)
    city = models.ForeignKey(City, on_delete=models.CASCADE,null = True)

    def __str__(self):
        return f'{self.shop_name}'

    def save(self, *args, **kwargs):
        # Double-check uniqueness before saving
        if not self.registration_number:
            self.registration_number = generate_registration_number()
            while ShopProfile.objects.filter(registration_number=self.registration_number).exists():
                self.registration_number = generate_registration_number()
        super().save(*args, **kwargs)

        

class Categories(models.Model):
    title = models.CharField(max_length =100)
    slug = models.SlugField(unique=True, blank=True,null = True)
    
    def __str__(self):
        return f'{self.title}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Categories'

    



class Product(models.Model):
    category = models.ForeignKey(Categories, on_delete = models.CASCADE)
    name = models.CharField(max_length =100)
    slug = models.SlugField(unique=True, blank=True)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete = models.CASCADE)
    description = RichTextUploadingField()
    main_image = models.ImageField(upload_to='Product')
    
    created_date = models.DateTimeField(auto_now_add = True)
    price = models.DecimalField(max_digits=10, decimal_places = 2)
    discount_price = models.DecimalField(max_digits=10, decimal_places = 2)
    available = models.BooleanField(default =True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE,null = True)
    city = models.ForeignKey(City, on_delete=models.CASCADE,null = True,blank = True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def formatted_created_at(self):
        from django.utils import timezone
        from datetime import datetime, timedelta

        diff = timezone.now() - self.created_date

        if diff < timedelta(seconds=60):
            return f"{diff.seconds} seconds ago"
        elif diff < timedelta(minutes=60):
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        elif diff < timedelta(hours=24):
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days} days ago"
        elif diff < timedelta(days=30):
            weeks = diff.days // 7
            return f"{weeks} weeks ago"
        elif diff < timedelta(days=365):
            months = diff.days // 30
            return f"{months} months ago"
        else:
            years = diff.days // 365
            return f"{years} years ago"
    
    @property
    def discount_percentage(self):
        if self.price and self.price > self.discount_price:
            discount = ((self.price - self.discount_price) / self.price) * 100
            return round(discount)
        return 0

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/gallery/')

    def __str__(self):
        return f"Image for {self.product.name}"

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.email}"

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        #return self.product.price * self.quantity
        return self.product.discount_price * self.quantity



class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('cancelled', 'Cancelled'),
        ('delivered','Delivered')
    )
    DELIVERY_CHOICES = [
        ('door', 'Door Delivery'),
        ('pickup', 'Pickup Station'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    delivery_method = models.CharField(
        max_length=10, 
        choices=DELIVERY_CHOICES, 
        default='door'
    )
    shipping_address = models.TextField(null = True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} by {self.user.email}"



class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    # Important: Price is saved here to prevent history changing if product price changes
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()



class SavedItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="saved_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.email} saved {self.product.name}"








class SellerPaymentMethod(models.Model):
    METHOD_TYPES = (
        ('bank', 'Bank Transfer'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
    )
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES)
    provider_name = models.CharField(max_length=100) # e.g., City Bank
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    routing_number = models.CharField(max_length=50, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_default:
            SellerPaymentMethod.objects.filter(seller=self.seller).update(is_default=False)
        super().save(*args, **kwargs)

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.ForeignKey(SellerPaymentMethod, on_delete=models.PROTECT,null =  True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)









#listings models
from django.db import models
from django.conf import settings
from cities_light.models import Country, City

class ListingCategory(models.Model):
    name = models.CharField(max_length=100) # e.g., Professional Services
    slug = models.SlugField(unique=True, blank=True,null = True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ListingSubCategory(models.Model):
    category = models.ForeignKey(ListingCategory, on_delete=models.CASCADE, related_name='listingsubcategories')
    name = models.CharField(max_length=100) # e.g., IT Developers
    slug = models.SlugField(unique=True, blank=True,null = True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} > {self.name}"

class Listing(models.Model):
    PRICING_MODELS = (
        ('fixed', 'Fixed'),
        ('hourly', 'Hourly'),
        ('negotiable', 'Negotiable'),
    )

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(
        ListingCategory, 
        on_delete=models.PROTECT, 
        related_name='listings',
        null=True, blank=True # Nullable initially for migration safety
    )
    views_count = models.PositiveIntegerField(default=0)
    subcategory = models.ForeignKey(ListingSubCategory, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True,null = True)
    
   
    description = models.TextField()
    main_image = models.ImageField(upload_to='listings/main/', help_text="Primary thumbnail")
    
    pricing_model = models.CharField(max_length=20, choices=PRICING_MODELS)
    price = models.DecimalField(max_digits=15, decimal_places=2)
    
    address = models.CharField(max_length=255, blank=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


    def save(self, *args, **kwargs):
        # 1. Sync Category from SubCategory
        if self.subcategory:
            self.category = self.subcategory.category

        # 2. Logic to determine if slug needs (re)generation
        if self.pk:
            # Fetch the existing title from the database to compare
            old_obj = Listing.objects.get(pk=self.pk)
            if old_obj.title != self.title:
                # Title changed! We need to regenerate the slug
                self.slug = self._generate_unique_slug(self.title)
        else:
            # Brand new listing
            if not self.slug:
                self.slug = self._generate_unique_slug(self.title)
            
        super().save(*args, **kwargs)

    def _generate_unique_slug(self, title):
        """Internal helper to ensure slug uniqueness"""
        base_slug = slugify(title)
        unique_slug = base_slug
        
        # Loop until we find a version of the slug that doesn't exist
        # Exclude self.pk so we don't conflict with our own record during updates
        while Listing.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
            unique_slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"
        
        return unique_slug

class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='listings/gallery/')
    
    def __str__(self):
        return f"Gallery image for {self.listing.title}"


class ListingView(models.Model):
    """Tracks daily views for the analytics chart"""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField(auto_now_add=True)
    count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('listing', 'date')



class ListingReport(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Report for {self.listing.title} - {self.reason}"
