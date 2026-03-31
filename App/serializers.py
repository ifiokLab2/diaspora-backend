from rest_framework import serializers
from .models import *
from django.db import transaction
import json
from django.contrib.auth.password_validation import validate_password


class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    re_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['re_new_password']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for the Gallery Images associated with a product.
    """
    class Meta:
        model = ProductImage
        fields = ['id', 'image']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Ensure Cloudinary returns the full secure URL
        if instance.image:
            representation['image'] = instance.image.url
        return representation


class ProductSerializer(serializers.ModelSerializer):
    # Nested gallery images
    images = ProductImageSerializer(many=True, read_only=True)
    
    # Custom Method Fields
    discount_percentage = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    
    # Read-only fields from related models
    country_name = serializers.ReadOnlyField(source='country.name')
    city_name = serializers.ReadOnlyField(source='city.name')
    category_name = serializers.ReadOnlyField(source='category.title')

    country = serializers.ReadOnlyField(source='country.id')
    city = serializers.ReadOnlyField(source='city.id')
    category = serializers.ReadOnlyField(source='category.id')

    latitude = serializers.ReadOnlyField(source='city.latitude')
    longitude = serializers.ReadOnlyField(source='city.longitude')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'main_image', 'images',
            'price', 'discount_price', 'available', 'discount_percentage',
            'category_name', 'country_name', 'city_name', 'is_saved',
            'created_date', 'longitude', 'latitude','country','city','category'
        ]

    def get_discount_percentage(self, obj):
        # Using getattr to safely check for the property/method
        try:
            return obj.discount_percentage
        except Exception:
            return 0

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Efficient check for saved items
            return SavedItem.objects.filter(user=request.user, product=obj).exists()
        return False

    def to_representation(self, instance):
        """
        This is where we force Cloudinary to return the URL 
        instead of the CloudinaryResource object.
        """
        representation = super().to_representation(instance)
        
        # Handle the main_image Cloudinary URL
        if instance.main_image:
            representation['main_image'] = instance.main_image.url
        else:
            representation['main_image'] = None
            
        return representation


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Categories
        fields = ['id', 'title', 'slug']




class OrderItemSerializer(serializers.ModelSerializer):
    # We use product_id for the input from the frontend
    product_id = serializers.IntegerField(write_only=True)
    product_name = serializers.ReadOnlyField(source='product.name')
    product_image = serializers.ImageField(source='product.main_image', read_only=True)
    productId = serializers.ReadOnlyField(source='product.id')
    
    class Meta:
        model = OrderItem
        fields = ['product_id','productId', 'product_name', 'product_image', 'quantity', 'price']
        read_only_fields = ['price','productId', 'product_name', 'product_image']# Price should be set by backend, not frontend

    def get_product_image(self, obj):
        if obj.product and obj.product.main_image:
            return obj.product.main_image.url
        return None
        

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            'id', 'items', 'delivery_method', 'shipping_address', 
            'total_amount', 'status', 'created_at','stripe_payment_intent'
        ]
        read_only_fields = ['id', 'status', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user

        with transaction.atomic():
            # 1. Create the parent Order
            order = Order.objects.create(user=user, **validated_data)

            # 2. Create the child OrderItems
            for item in items_data:
                product = Product.objects.get(id=item['product_id'])
                
                # Security: Use the actual current price from the DB, 
                # don't trust the price sent from the frontend!
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price=product.discount_price if product.discount_price else product.price
                )
            
            return order

            

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'subtotal']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_price']






class CustomerProfileSerializer(serializers.ModelSerializer):
    # We use PrimaryKeyRelatedField for incoming data (IDs)
    # but we can add secondary fields for displaying names if needed
    country_name = serializers.ReadOnlyField(source='country.name')
    city_name = serializers.ReadOnlyField(source='city.name')

    class Meta:
        model = CustomerProfile
        fields = [
            'phone', 'phone_secondary', 'address', 'notes', 
            'country', 'city', 'country_name', 'city_name', 'gender'
        ]

class UserMeSerializer(serializers.ModelSerializer):
    profile = CustomerProfileSerializer()

    class Meta:
        model = myuser
        fields = ['first_name', 'last_name', 'email', 'profile']
        read_only_fields = ['email']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update User
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()

        # Update Profile
        if profile_data:
            profile, _ = CustomerProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance



#seller

class ShopProfileSerializer(serializers.ModelSerializer):
    registration_number = serializers.CharField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # We keep this as an ImageField for the 'Write' part (uploads)
    # But we'll handle the 'Read' part to return the Cloudinary URL
    logo = serializers.ImageField(required=False, allow_null=True)
    
    country_name = serializers.CharField(source='country.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = ShopProfile
        fields = [
            'id', 'user', 'shop_name', 'business_type', 'phone_number', 
            'business_address', 'bank_name', 'account_number', 'sort_code', 
            'registration_number', 'country', 'city', 'country_name', 'city_name',
            'logo',
        ]

    def to_representation(self, instance):
        """Customizing the output to ensure logo is a full URL"""
        representation = super().to_representation(instance)
        # Check if logo exists and return the .url property
        if instance.logo:
            # CloudinaryField returns an object; .url provides the CDN link
            representation['logo'] = instance.logo.url
        return representation


class ShopProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopProfile
        fields = [
            'shop_name', 'business_type', 'phone_number', 
            'business_address', 'bank_name', 'account_number', 
            'sort_code', 'city', 'country', 'logo'
        ]

    def update(self, instance, validated_data):
        # Cloudinary handles the upload to the cloud automatically
        # when the 'logo' file is assigned to the model field.
        return super().update(instance, validated_data)

    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.logo:
            representation['logo'] = instance.logo.url
        return representation









class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Main Serializer for Creating and Updating Products with Gallery Support.
    """
    category_name = serializers.ReadOnlyField(source='category.title')
    country_name = serializers.ReadOnlyField(source='country.name')
    city_name = serializers.ReadOnlyField(source='city.name')
    
    # We define main_image explicitly to ensure ImageField validation
    main_image = serializers.ImageField(required=True)
    
    # gallery_images: Used for incoming File uploads (Write-only)
    gallery_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    
    # images: Used for outgoing JSON response (Read-only)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'discount_price', 
            'main_image', 'gallery_images', 'images', 'category', 'category_name', 
            'country', 'country_name', 'city', 'city_name', 
            'available', 'created_date'
        ]
        read_only_fields = ['slug', 'created_date']

    def validate(self, data):
        """
        Custom validation for business logic.
        """
        price = data.get('price')
        discount_price = data.get('discount_price')

        # 1. Price Validation
        if discount_price is not None and price is not None:
            if discount_price > price:
                raise serializers.ValidationError({
                    "discount_price": "Discount price cannot be greater than the original price."
                })
        
        # 2. Location Integrity Validation
        country = data.get('country')
        city = data.get('city')
        if country and city and city.country != country:
            raise serializers.ValidationError({
                "city": "The selected city does not belong to the selected country."
            })

        return data

    def create(self, validated_data):
        """
        Handles the creation of the Product and its associated Gallery Images.
        """
        # Extract gallery images before creating the product
        gallery_data = validated_data.pop('gallery_images', [])
        
        # Automatically assign the seller from the request context
        validated_data['seller'] = self.context['request'].user
        
        # Create the Product instance
        product = Product.objects.create(**validated_data)
        
        # Create ProductImage entries for each uploaded gallery file
        for image_file in gallery_data:
            ProductImage.objects.create(product=product, image=image_file)
            
        return product

    def update(self, instance, validated_data):
        """
        Handles updates, including adding new images to the gallery.
        """
        gallery_data = validated_data.pop('gallery_images', None)
        
        # Update the basic product fields
        instance = super().update(instance, validated_data)
        
        # If new gallery images were provided, append them to the existing gallery
        if gallery_data:
            for image_file in gallery_data:
                ProductImage.objects.create(product=instance, image=image_file)
        
        return instance

    def to_representation(self, instance):
        """
        Customizes the output format for Cloudinary URLs.
        """
        representation = super().to_representation(instance)
        if instance.main_image:
            representation['main_image'] = instance.main_image.url
        return representation





class SellerOrderSerializer(serializers.ModelSerializer):
    # Using 'source' to reach into the ForeignKey 'order'
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.CharField(source=f'order.user.first_name', read_only=True)
    customer_email = serializers.CharField(source='order.user.email', read_only=True)
    status = serializers.CharField(source='order.status', read_only=True)
    delivery_method = serializers.CharField(source='order.delivery_method', read_only=True)
    created_at = serializers.DateTimeField(source='order.created_at', read_only=True)
    
    # Custom fields for the table
    product_name = serializers.CharField(source='product.name', read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order_id', 'product_name', 'customer_name', 
            'customer_email', 'price', 'quantity', 'line_total', 
            'status', 'delivery_method', 'created_at'
        ]

    def get_line_total(self, obj):
        return obj.price * obj.quantity







class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerPaymentMethod
        fields = '__all__'
        read_only_fields = ['seller']

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    # This nested detail allows the frontend table to show "Bank Transfer" instead of just an ID
    method_details = PaymentMethodSerializer(source='method', read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = ['id', 'amount', 'method', 'method_details', 'status', 'created_at']
        read_only_fields = ['status']










class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ['id', 'image']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.image:
            rep['image'] = instance.image.url
        return rep


class ListingSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingSubCategory
        fields = '__all__'


class SubCategoryMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingSubCategory
        fields = ['id', 'name', 'slug']

class CategoryMenuSerializer(serializers.ModelSerializer):
    # This name must match the related_name in your ForeignKey
    subs = SubCategoryMenuSerializer(source='listingsubcategories', many=True, read_only=True)

    class Meta:
        model = ListingCategory
        fields = ['id', 'name', 'slug', 'subs']



class ListingSerializer(serializers.ModelSerializer):
    additional_images = ListingImageSerializer(many=True, read_only=True)
    category_name = serializers.ReadOnlyField(source='category.name')
    subcategory_name = serializers.ReadOnlyField(source='subcategory.name')
    seller_first_name = serializers.ReadOnlyField(source='seller.first_name')
    seller_last_name = serializers.ReadOnlyField(source='seller.last_name')
    city_name = serializers.ReadOnlyField(source='city.name')
    country_name = serializers.ReadOnlyField(source='country.name')

    class Meta:
        model = Listing
        fields = '__all__'
        read_only_fields = ['seller', 'is_active', 'created_at', 'slug', 'category']

    def to_internal_value(self, data):
        # Handle stringified JSON metadata from Frontend
        if isinstance(data.get('metadata'), str):
            data = data.copy()
            try:
                data['metadata'] = json.loads(data['metadata'])
            except (ValueError, TypeError):
                data['metadata'] = {}
        return super().to_internal_value(data)

    def to_representation(self, instance):
        """Converts CloudinaryResource to URL string for the API response"""
        rep = super().to_representation(instance)
        if instance.main_image:
            rep['main_image'] = instance.main_image.url
        return rep
 