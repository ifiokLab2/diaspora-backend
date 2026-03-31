from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from .models import *
from .serializers import *
from rest_framework import generics
from rest_framework import status, parsers
from rest_framework.pagination import LimitOffsetPagination
import stripe
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import transaction
from django.db import IntegrityError
from django.db.models import Q
from django.conf import settings
stripe.api_key = settings.STRIPE_SECRET_KEY
from rest_framework.pagination import PageNumberPagination
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, F, Count
from django.core.paginator import Paginator

from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })

class ProductCategoryListView(APIView):
    """
    Manual APIView handling Category filtering and LimitOffset Pagination
    to support Infinite Scroll in Next.js.
    """
    def get(self, request):
        # 1. Filter Queryset by Category Slug
        category_slug = request.query_params.get('category')
        queryset = Product.objects.all()
        
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # 2. Initialize Paginator
        paginator = LimitOffsetPagination()
        
        # 3. Paginate the Queryset
        # This looks for 'limit' and 'offset' in request.query_params
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = ProductSerializer(page, many=True, context={'request': request})
            # Returns a structured response: { "count": X, "next": URL, "previous": URL, "results": [...] }
            return paginator.get_paginated_response(serializer.data)

        # Fallback if pagination is not triggered
        serializer = ProductSerializer(queryset, many=True, context={'request': request})
        print('serializer.data@@@@:',serializer.data)
        return Response(serializer.data)

# --- CUSTOMER REGISTRATION ---
class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        #print(' data:', data)
        try:
            user = myuser.objects.create_user(
                email=data.get('email'),
                password=data.get('password'),
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                is_customer=True,
                is_seller=False
            )
            
            # Customers get a cart immediately
            Cart.objects.create(user=user)
            
            return Response({"message": "Customer account created"}, status=status.HTTP_201_CREATED)
        except IntegrityError:
            existing_user = myuser.objects.filter(email=data.get('email')).first()
            
            if existing_user:
                role = "seller" if existing_user.is_seller else "customer"
            else:
                role = "unknown" # Fallback if error wasn't due to email conflict
            return Response({"error": f"Email already exists. This account is already registered as a {role}"}, status=status.HTTP_400_BAD_REQUEST)

# --- SELLER REGISTRATION ---
class SellerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        
        try:
            user = myuser.objects.create_user(
                email=data.get('email'),
                password=data.get('password'),
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                is_customer=False,
                is_seller=True,
                is_staff=True  # Usually sellers need access to some admin features
            )
            role = "seller" if user.is_seller else "customer"
            # You might create a 'Store' or 'Profile' model here for Sellers
            return Response({"message": "Seller account created"}, status=status.HTTP_201_CREATED)
        except IntegrityError:
            existing_user = myuser.objects.filter(email=data.get('email')).first()
            
            if existing_user:
                role = "seller" if existing_user.is_seller else "customer"
            else:
                role = "unknown" # Fallback if error wasn't due to email conflict
            return Response({"error": f"Email already exists. this account is already registered as a {role}"}, status=status.HTTP_400_BAD_REQUEST)


class BaseLoginView(APIView):
    permission_classes = [AllowAny]
    role_flag = None  # To be set by subclasses ('is_customer' or 'is_seller')

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        # SimpleJWT uses 'username' for authentication even if your model uses 'email'
        user = authenticate(username=email, password=password)

        if not user:
            print('Invalid email or password.')
            return Response(
                {"error": "Invalid email or password.","exist":False}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 1. Role Verification Gate
        # Ensures a seller can't log in through the customer portal and vice versa
        if not getattr(user, self.role_flag, False):
            role_name = self.role_flag.split('_')[1]
            role = ""
            if user.is_staff:
                role = "staff"
            if user.is_seller:
                role = "seller"
            if user.is_customer:
                role = "customer"
            return Response(
                {"error": f"This account is registered as a {role}. Please create a {role_name} account to continue.","exist":True},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Check for Shop Profile (Only for Sellers)
        has_shop_profile = False
        if user.is_seller:
            has_shop_profile = hasattr(user, 'shop_profile')

        # 3. Generate Tokens
        refresh = RefreshToken.for_user(user)

        # 4. Construct Response
        # Key names here MUST match your AuthContext.tsx User interface
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": "seller" if user.is_seller else "customer",
                "hasShopProfile": has_shop_profile  # Used by Next.js router
            }
        }, status=status.HTTP_200_OK)

# Implementation Classes
class CustomerLoginView(BaseLoginView):
    role_flag = 'is_customer'

class SellerLoginView(BaseLoginView):
    role_flag = 'is_seller'






class LocationDataView(APIView):
    """Provides lists of countries and cities for the frontend selects"""
    def get(self, request):
        countries = Country.objects.all().values('id', 'name')
        # Optimization: Only fetch cities for a specific country if provided
        country_id = request.query_params.get('country_id')
        
        cities = []
        if country_id:
            cities = City.objects.filter(country_id=country_id).values('id', 'name')[:100]
        print("countries:", list(countries),"city:", list(cities))
        return Response({
            "countries": list(countries),
            "cities": list(cities)
        })

class ListingCitySearchAPIView(generics.ListAPIView):
    """API to search for cities to populate the frontend dropdown"""
    def get(self, request):
        query = request.GET.get('q', '')
        if len(query) < 2:
            return Response([])
            
        # Search cities and include their country info
        cities = City.objects.filter(name__icontains=query).select_related('country')[:10]
        
        return Response([{
            'id': city.id,
            'name': f"{city.name}, {city.country.name}",
            'country_id': city.country.id
        } for city in cities])

class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        
        return Response({
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": profile.phone,
            "phone_secondary": profile.phone_secondary,
            "address": profile.address,
            "notes": profile.notes,
            "country": profile.country.id if profile.country else "",
            "country_name": profile.country.name if profile.country else "",
            "city": profile.city.id if profile.city else "",
            "city_name": profile.city.name if profile.city else "",
            "gender": profile.gender,
        })
    
    def patch(self, request):
        # We wrap the profile-related fields into a 'profile' key
        # to match the Nested Serializer's expected format
        data = request.data.copy()
        profile_fields = ['phone', 'phone_secondary', 'address', 'notes', 'country', 'city', 'gender']
        
        profile_data = {}
        for field in profile_fields:
            if field in data:
                profile_data[field] = data.pop(field)
        
        data['profile'] = profile_data

        serializer = UserMeSerializer(request.user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class ProductSearchListView(APIView):
    """
    Handles combined search for Products, Services, and Location 
    with Infinite Scroll pagination.
    """
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]
    def get(self, request, *args, **kwargs):
        print("--- ALL REQUEST HEADERS ---")
        for header, value in request.headers.items():
            print(f"{header}: {value}")

        # 2. Specifically check for the Authorization Token
        auth_header = request.headers.get('Authorization')
        print(f"\n--- AUTH HEADER FOUND: {auth_header} ---")

        # 3. Check if DRF identified the user based on that header
        print(f"--- REQUEST USER: {request.user} (Authenticated: {request.user.is_authenticated}) ---")
        # 1. Extract parameters from the WHATWG URLSearchParams
        search_query = request.query_params.get('search', '').strip()
        service_query = request.query_params.get('service', '').strip()
        location_query = request.query_params.get('location', '').strip()

        # 2. Start with a clean QuerySet
        # select_related avoids the N+1 problem for category/store details
        queryset = Product.objects.all().select_related('category')

        # 3. Apply Filters (Case-insensitive containment)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )

        

        # 4. Default Ordering (Crucial for consistent pagination)
        queryset = queryset.order_by('-created_date')

        # 5. Manual Pagination for APIView
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        
        #serializer = ProductSerializer(result_page, many=True)
        serializer = ProductSerializer(result_page, context={'request': request},many=True)
        
        # Returns the 'count' and 'results' keys your Next.js frontend expects
        print('serializer.data@@@@:',serializer.data)
        return paginator.get_paginated_response(serializer.data)



class ListingsSearchListView(APIView):
    """
    Handles combined search for Listings, Services, and Location 
    with Infinite Scroll pagination.
    """
    permission_classes = [AllowAny]
    #authentication_classes = [JWTAuthentication]
    def get(self, request, *args, **kwargs):
        
        # 1. Extract parameters from the WHATWG URLSearchParams
        search_query = request.query_params.get('search', '').strip()
        service_query = request.query_params.get('listings', '').strip()
        location_query = request.query_params.get('location', '').strip()

        # 2. Start with a clean QuerySet
        # select_related avoids the N+1 problem for category/store details
        queryset = Listing.objects.all().select_related(
            'category', 'subcategory', 'city', 'country'
        )

        if service_query:
            print('service_query:',service_query)
            queryset = queryset.filter(
                Q(title__icontains= service_query) | 
                 Q(category__name__icontains= service_query) | 
                Q(subcategory__name__icontains= service_query) | 
                Q(description__icontains= service_query)
               
            )
        if  location_query:
            print('location_query:',location_query)
            queryset = queryset.filter(
                Q(city__name__icontains= location_query) |
                Q(country__name__icontains= location_query)
            )

        # 3. Apply Filters (Case-insensitive containment)
        if service_query and location_query:
            print('location_query222:',location_query)
            queryset = queryset.filter(
                Q(title__icontains= service_query) | 
                 Q(category__name__icontains= service_query) | 
                Q(subcategory__name__icontains= service_query) | 
                Q(description__icontains= service_query) |
                Q(city__display_name__icontains=location_query) |
                Q(city__name__icontains= location_query) |
                Q(country__name__icontains= location_query)
            )

        

        # 4. Default Ordering (Crucial for consistent pagination)
        queryset = queryset.order_by('-created_at')

        # 5. Manual Pagination for APIView
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        
        #serializer = ProductSerializer(result_page, many=True)
        serializer = ListingSerializer(result_page,many=True)
        
        # Returns the 'count' and 'results' keys your Next.js frontend expects
        print('serializer.data@@@@:',serializer.data)
        return paginator.get_paginated_response(serializer.data)


class ProductSuggestionView(APIView):
    """
    Lightning-fast endpoint for search suggestions.
    """
    def get(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response([])

        # We only get id, name, and slug to minimize data transfer
        """queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )"""
        suggestions = Product.objects.filter(
            name__icontains=query, 
            available=True
        ).values('id', 'name', 'slug')[:5]

        return Response(list(suggestions))


class ProductListView(APIView):
    """
    List all active products.
    Next.js URL: /api/products/
    """
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        products = Product.objects.filter(available = True).order_by('-created_date')
        serializer = ProductSerializer(products, context={'request': request},many=True)
        #serializer = ProductSerializer(products, many=True)
        print('serializer.data@@@@:',serializer.data)
        return Response(serializer.data)


class ProductDetailView(APIView):
    # Allow anyone to view product details
    permission_classes = [AllowAny]
    # Use JWTAuthentication so request.user is populated if a token is sent
    authentication_classes = [JWTAuthentication]

    def get(self, request, slug):
        # 1. Retrieve the main product
        product = get_object_or_404(Product, slug=slug)
        
        # 2. Serialize the main product
        # IMPORTANT: context={'request': request} is required for the SerializerMethodField
        serializer = ProductSerializer(product, context={'request': request})
        
        # 3. Retrieve Related Products (Same category, excluding current product)
        related_products = Product.objects.filter(
            category=product.category
        ).exclude(id=product.id)[:4]
        
        # 4. Serialize related products with the same context
        related_serializer = ProductSerializer(
            related_products, 
            many=True, 
            context={'request': request}
        )

        # 5. Build and return the combined response
        #print('serializer.data:',serializer.data)
        return Response({
            "product": serializer.data,
            "related": related_serializer.data
        }, status=status.HTTP_200_OK)


class ToggleSavedItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        product = Product.objects.get(id=product_id)
        saved_item = SavedItem.objects.filter(user=request.user, product=product)

        if saved_item.exists():
            saved_item.delete()
            return Response({"saved": False, "message": "Removed from saved items"})
        
        SavedItem.objects.create(user=request.user, product=product)
        return Response({"saved": True, "message": "Added to saved items"})

class CategoryListView(APIView):
    """
    List all categories.
    Next.js URL: /api/products/categories/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)
class CartView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        #print('serializer.data:',serializer.data)
        return Response(serializer.data)

class ClearCartView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request):
        try:
            # Assuming a OneToOne relationship between User and Cart
            cart = Cart.objects.get(user=request.user)
            # Efficiently delete all items in the cart
            CartItem.objects.filter(cart=cart).delete()
            
            return Response(
                {"message": "Cart cleared successfully"}, 
                status=status.HTTP_200_OK # Changed to 200 so frontend sees the message
            )
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        cart, _ = Cart.objects.get_or_create(user=request.user)
        
        item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()
        
        return Response({"message": "Item added"}, status=201)


class UpdateCartQuantityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        # This can be 1 (to add) or -1 (to remove one)
        change_quantity = int(request.data.get('quantity', 1)) 
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)

        if not created:
            item.quantity += change_quantity
        else:
            # If item is new but quantity is negative, that's an error
            item.quantity = max(0, change_quantity)

        # If quantity hits 0 or less, we just remove the item
        if item.quantity <= 0:
            item.delete()
            return Response({"message": "Item removed from cart"}, status=200)
        
        item.save()
        return Response({"message": "Cart updated", "new_quantity": item.quantity}, status=200)


class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, product_id):
        # We find the cart for the user and the specific item
        cart = get_object_or_404(Cart, user=request.user)
        item = get_object_or_404(CartItem, cart=cart, product_id=product_id)
        
        item.delete()
        return Response({"message": "Item removed from cart"}, status=204)






from django.db import transaction


class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # 1. Save Order (calls create() in Serializer)
                    order = serializer.save()

                    # 2. Create Stripe Checkout Session
                    checkout_session = stripe.checkout.Session.create(
                        payment_method_types=['card'],
                        line_items=[{
                            'price_data': {
                                'currency': 'gbp',
                                'product_data': {
                                    'name': f"Order #{order.id} - DiasporaBlack",
                                },
                                'unit_amount': int(order.total_amount * 100), # Amount in pence
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=f"{settings.FRONTEND_URL}/customer/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
                        cancel_url=f"{settings.FRONTEND_URL}/cart",
                        metadata={
                            'order_id': order.id,
                            'user_email': request.user.email
                        }
                    )

                    # 3. Store Session ID for tracking
                    order.stripe_payment_intent = checkout_session.id
                    order.save()

                    return Response(
                        {'checkout_url': checkout_session.url, 'order_id': order.id}, 
                        status=status.HTTP_201_CREATED
                    )

            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

   
    def get(self, request):
        # 'items__product' tells Django to fetch the items AND their products in one go
        orders = Order.objects.filter(user=request.user)\
                              .prefetch_related('items__product')\
                              .order_by('-created_at')
        
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        print('serializer.data:',serializer.data)
        return Response(serializer.data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        # We filter by user=request.user so users can't guess IDs of other people's orders
        order = get_object_or_404(Order, id=id, user=request.user)
        
        # Serialize the order. The serializer will include the nested items.
        serializer = OrderSerializer(order)
        print('serializer.data:',serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)



class StripeWebhookView(APIView):
    permission_classes = [AllowAny] # Stripe must be able to reach this

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            return HttpResponse(status=400) # Invalid payload
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400) # Invalid signature

        # Handle successful payment
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            order_id = session.get('metadata', {}).get('order_id')

            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    order.status = 'paid'
                    order.save()
                    # Trigger email confirmation here if needed
                except Order.DoesNotExist:
                    return HttpResponse(status=404)

        return HttpResponse(status=200)



@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session['metadata']['order_id']
        order = Order.objects.get(id=order_id)
        order.status = 'paid'
        order.stripe_payment_intent = session['payment_intent']
        order.save()
        # Optionally clear the user's cart here
        Cart.objects.get(user=order.user).items.all().delete()


    return HttpResponse(status=200)


class SavedItemsListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # 1. Get all saved items for the current user
        # We use select_related to optimize the database query
        saved_items = SavedItem.objects.filter(user=request.user).select_related('product')
        
        # 2. Extract the product objects
        products = [item.product for item in saved_items]
        
        # 3. Serialize the products (passing request for is_saved check)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        print(serializer.data)
        
        return Response(serializer.data)



#seller


class CreateShopProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        user = request.user

        # 1. Prevent duplicate profiles
        if hasattr(user, 'shop_profile'):
            return Response(
                {"error": "You already have a shop profile."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validate data
        serializer = ShopProfileSerializer(data=request.data)
        if serializer.is_valid():
            # 3. Save with the authenticated user
            # The registration_number is auto-generated in the Model's save()
            profile = serializer.save(user=user)

            # 4. Update the user's onboarding status
            user.has_shop_profile = True
            user.save()

            # 5. Return the created profile including the new registration_number
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





class ShopProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # MultiPartParser is required for file uploads (logos)
    # FormParser is required for the text fields in FormData
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def patch(self, request, *args, **kwargs):
        try:
            # Get the profile belonging to the logged-in user
            profile = request.user.shop_profile
        except ShopProfile.DoesNotExist:
            return Response(
                {"error": "Shop profile not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Pass partial=True so the user doesn't have to send EVERY field
        serializer = ShopProfileUpdateSerializer(
            profile, 
            data=request.data, 
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class GetShopProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.shop_profile
            serializer = ShopProfileSerializer(profile)
            print('serializer.data:',serializer.data)
            return Response(serializer.data)
        except ShopProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )






class ProductListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get(self, request):
        """List products belonging to the logged-in seller"""
        products = Product.objects.filter(seller=request.user).order_by('-created_date')
        #products = Product.objects.all()
        #serializer = ProductCreateSerializer(products, many=True)
        #print('serializer.data:',serializer.data)
        #return Response(serializer.data)

        #
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(products, request)
        serializer = ProductCreateSerializer(result_page, many=True)
        print('serializer.data@@@:',serializer.data)
        
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Pass the request context here! 
        serializer = ProductCreateSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save(
                available=True
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        product_id = request.query_params.get('id')
        try:
            # Ensure the product belongs to the requester
            product = Product.objects.get(id=product_id, seller=request.user)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # 'partial=True' allows updating only sent fields (e.g., just the price)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request):
        product_id = request.query_params.get('id')
        try:
            product = Product.objects.get(id=product_id, seller=request.user)
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

class CategoryListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Categories.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


        


class SellerOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Filter OrderItems where the product's seller is the logged-in user
        # 2. Use select_related to optimize the SQL query (prevents N+1 problem)
       # orders = OrderItem.objects.filter(
        #    product__seller=request.user
        #).select_related('order', 'order__user').order_by('-order__created_at')
        order_items = OrderItem.objects.filter(
            product__seller=request.user
        ).select_related('order', 'order__user', 'product').order_by('-order__created_at')

        

        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(order_items, request)
        serializer = SellerOrderSerializer(result_page, many=True)
        
        return paginator.get_paginated_response(serializer.data)

    def patch(self, request, pk):
        """
        Optional: Allow sellers to update the status (e.g., from Processing to Shipped)
        """
        try:
            order_item = OrderItem.objects.get(pk=pk, product__seller=request.user)
            new_status = request.data.get('status')
            if new_status:
                order_item.status = new_status
                order_item.save()
                return Response({"message": "Status updated"}, status=status.HTTP_200_OK)
            return Response({"error": "No status provided"}, status=status.HTTP_400_BAD_REQUEST)
        except OrderItem.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)






class SellerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        seller = request.user
        now = timezone.now()
        
        # 1. Define Time Windows for Dynamic Changes
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0)
        last_month_end = this_month_start - timedelta(seconds=1)
        last_month_start = (this_month_start - timedelta(days=28)).replace(day=1)

        def get_period_stats(start_date, end_date):
            qs = OrderItem.objects.filter(
                product__seller=seller,
                order__created_at__range=(start_date, end_date)
            )
            revenue = qs.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0
            orders = qs.values('order').distinct().count()
            units = qs.aggregate(total=Sum('quantity'))['total'] or 0
            return float(revenue), orders, units

        # Fetch Data for Dynamic Metrics
        curr_rev, curr_orders, curr_units = get_period_stats(this_month_start, now)
        prev_rev, prev_orders, prev_units = get_period_stats(last_month_start, last_month_end)

        def calc_change(curr, prev):
            if prev == 0: return "+100%" if curr > 0 else "0%"
            diff = ((curr - prev) / prev) * 100
            return f"{'+' if diff >= 0 else ''}{round(diff, 1)}%"

        # 2. Define trend_qs (The missing variable)
        # We look at the last 6 months of data
        six_months_ago = now - timedelta(days=180)
        trend_qs = OrderItem.objects.filter(
            product__seller=seller,
            order__created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('order__created_at')
        ).values('month').annotate(
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('month')

        # 3. Define topProducts
        top_products_qs = OrderItem.objects.filter(product__seller=seller) \
            .values(name=F('product__name')) \
            .annotate(
                sales=Sum('quantity'), 
                revenue=Sum(F('price') * F('quantity'))
            ).order_by('-revenue')[:5]

        # 4. Define categoryBreakdown
        # Assuming your Product model has a 'category' field with a 'name'
        categories_qs = OrderItem.objects.filter(product__seller=seller) \
            .values(name=F('product__category__title')) \
            .annotate(
                # Sum (price * quantity) for all items in this category
                value=Sum(F('price') * F('quantity')) 
            ) \
            .order_by('-value')
        
        print('categories_qs:', categories_qs)
        return Response({
            "metrics": [
                {
                    "label": "Total Revenue", 
                    "value": f" £{curr_rev}", 
                    "change": calc_change(curr_rev, prev_rev),
                    "positive": curr_rev >= prev_rev
                },
                {
                    "label": "Total Orders", 
                    "value": str(curr_orders), 
                    "change": calc_change(curr_orders, prev_orders),
                    "positive": curr_orders >= prev_orders
                },
                {
                    "label": "Units Sold", 
                    "value": str(curr_units), 
                    "change": calc_change(curr_units, prev_units),
                    "positive": curr_units >= prev_units
                },
                {
                    "label": "Growth Rate", 
                    "value": calc_change(curr_rev, prev_rev).replace('+', ''), 
                    "change": "vs last month",
                    "positive": curr_rev >= prev_rev
                },
            ],
            "salesTrend": [
                {"month": x['month'].strftime('%b'), "revenue": float(x['revenue'])} 
                for x in trend_qs
            ],
            "topProducts": [
                {"name": p['name'], "sales": p['sales'], "revenue": float(p['revenue'])} 
                for p in top_products_qs
            ],
            "categoryBreakdown": [
                    {
                        "name": c['name'] if c['name'] else "General", 
                        "value": float(c['value']) # Convert Decimal to float for JSON
                    } 
                    for c in categories_qs
                ]
        })








class SellerDashboardAnalytics(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        seller = request.user
        now = timezone.now()
        period = request.query_params.get('period', 'weekly')
        
        # Define statuses that count as "earned" revenue
        earned_statuses = ['paid', 'shipped', 'delivered']#remve pending in production

        # 1. TOP METRICS CALCULATION
        total_balance = OrderItem.objects.filter(
            product__seller=seller, 
            order__status__in=earned_statuses
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        today_sales = OrderItem.objects.filter(
            product__seller=seller, 
            order__created_at__date=now.date(),
            order__status__in=earned_statuses
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        new_orders = OrderItem.objects.filter(
            product__seller=seller, 
            order__status='pending'
        ).count()

        pending_shipment = OrderItem.objects.filter(
            product__seller=seller, 
            order__status='paid'
        ).count()

        # 2. PAYOUT BALANCE (Earned Revenue - Successful/Pending Withdrawals)
        total_earned = OrderItem.objects.filter(
            product__seller=seller, 
            order__status__in=['paid', 'shipped', 'delivered'] #production ['paid', 'shipped', 'delivered']
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        #WithdrawalRequest.objects.all().delete()
        total_withdrawn = WithdrawalRequest.objects.filter(
            seller=seller, 
            status__in=['pending', 'approved', 'completed']
        ).aggregate(t=Sum('amount'))['t'] or 0
        
        payout_balance = max(0, total_earned - total_withdrawn)

        print('total_earned:',total_earned,'total_withdrawn:',total_withdrawn,'payout_balance:',payout_balance)

        # 3. REVENUE TREND (Current Month vs Last Month)
        last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        current_month_rev = OrderItem.objects.filter(
            product__seller=seller,
            order__created_at__month=now.month,
            order__created_at__year=now.year,
            order__status__in=earned_statuses
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        last_month_rev = OrderItem.objects.filter(
            product__seller=seller,
            order__created_at__month=last_month_start.month,
            order__created_at__year=last_month_start.year,
            order__status__in=earned_statuses
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        trend_val = 0
        if last_month_rev > 0:
            trend_val = ((current_month_rev - last_month_rev) / last_month_rev) * 100

        # 4. CHART DATA WITH GAP FILLING
        chart_data = []
        if period == 'monthly':
            sales_qs = OrderItem.objects.filter(
                product__seller=seller,
                order__created_at__year=now.year,
                order__status__in=earned_statuses
            ).annotate(m=TruncMonth('order__created_at')).values('m').annotate(total=Sum(F('price')*F('quantity')))
            sales_dict = {item['m'].month: float(item['total']) for item in sales_qs}
            for m_idx in range(1, 13):
                m_date = now.replace(month=m_idx, day=1)
                chart_data.append({"name": m_date.strftime('%b'), "total": sales_dict.get(m_idx, 0.0)})

        elif period == 'yearly':
            sales_qs = OrderItem.objects.filter(
                product__seller=seller,
                order__status__in=earned_statuses
            ).annotate(y=TruncYear('order__created_at')).values('y').annotate(total=Sum(F('price')*F('quantity')))
            sales_dict = {item['y'].year: float(item['total']) for item in sales_qs}
            for i in range(4, -1, -1):
                y_val = now.year - i
                chart_data.append({"name": str(y_val), "total": sales_dict.get(y_val, 0.0)})

        else: # weekly
            start_date = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            sales_qs = OrderItem.objects.filter(
                product__seller=seller,
                order__created_at__gte=start_date,
                order__status__in=earned_statuses
            ).annotate(d=TruncDay('order__created_at')).values('d').annotate(total=Sum(F('price')*F('quantity')))
            sales_dict = {item['d'].date(): float(item['total']) for item in sales_qs}
            for i in range(6, -1, -1):
                day_obj = (now - timedelta(days=i)).date()
                chart_data.append({"name": day_obj.strftime('%a'), "total": sales_dict.get(day_obj, 0.0)})

        # 5. RECENT ORDERS (Clean Data with unique row_id)
        recent_items = OrderItem.objects.filter(
            product__seller=seller
        ).select_related('order', 'order__user').order_by('-order__created_at')[:5]

        recent_orders = [
            {
                "row_id": item.id,
                "id": f"ORD-{item.order.id}",
                "customer": f"{item.order.user.first_name} {item.order.user.last_name}".strip() or item.order.user.email,
                "product": item.product.name if item.product else "N/A",
                "date": item.order.created_at.strftime('%b %d, %Y'),
                "amount": f"{item.price * item.quantity:,}",
                "status_key": item.order.status,
                'main_image':item.product.main_image.url if item.product.main_image else "",
                "status_display": item.order.get_status_display(),
            } for item in recent_items
        ]

        # 6. PAYMENT METHOD DATA
        default_method = SellerPaymentMethod.objects.filter(seller=seller, is_default=True).first()
        payment_info = None
        if default_method:
            raw_acc = default_method.account_number
            payment_info = {
                "type": default_method.get_method_type_display().upper(),
                "provider": default_method.provider_name.upper(),
                "id": default_method.id,
                "account_name": default_method.account_name.upper(),
                "display_number": f"•••• •••• •••• {raw_acc[-4:]}" if len(raw_acc) > 4 else raw_acc,
                "icon": "🏦" if default_method.method_type == 'bank' else "📱",
                "is_mobile": default_method.method_type != 'bank'
            }

        return Response({
            "total_balance": f"{payout_balance:,}",
            "payout_balance": f"{payout_balance:,}",
            "today_sales": f"{today_sales:,}",
            "new_orders": str(new_orders),
            "pending_shipment": str(pending_shipment),
            "revenue_trend": f"{abs(trend_val):.1f}%",
            "trend_positive": trend_val >= 0,
            "chart_data": chart_data[0:6],
            "recent_orders": recent_orders,
            "payment_method": payment_info
        })




class SellerPayoutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        seller = request.user
        now = timezone.now()
        
        # 1. Total Earnings (All orders that are paid/shipped)
        EARNED_STATUSES = ['paid', 'shipped', 'delivered']
        total_earnings = OrderItem.objects.filter(
            product__seller=seller,
            order__status__in=['paid','delivered', 'shipped']#production ['paid', 'shipped', 'delivered']
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        # 2. This Month's Earnings
        this_month = OrderItem.objects.filter(
            product__seller=seller,
            order__status__in=['paid', 'shipped','delivered'],
            order__created_at__month=now.month,
            order__created_at__year=now.year
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

        # 3. Pending Amount (Orders not yet shipped/paid)
        pending_balance = OrderItem.objects.filter(
            product__seller=seller,
            order__status='pending'
        ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0
        pending_items = OrderItem.objects.filter(
            product__seller=seller,
            order__status='pending'
        )
        for item in pending_items:
            product_name = item.product.name
            order_status = item.order.status
            item_price = item.price
            qty = item.quantity
        
            print(f"Product: {product_name} | Status: {order_status} | Subtotal: {item_price * qty}")

        # 4. Total Withdrawn (To calculate Available Balance)
        total_withdrawn = WithdrawalRequest.objects.filter(
            seller=seller,
            status__in=['pending', 'processing', 'completed']
        ).aggregate(t=Sum('amount'))['t'] or 0

        available_balance = float(total_earnings) - float(total_withdrawn)
        print('available_balance:',available_balance)
        print(' pending_balance:', pending_balance)
        print('total_earnings:', total_earnings)
        # History and Methods
        history = WithdrawalRequest.objects.filter(seller=seller).order_by('-created_at')
        
        return Response({
            "available_balance": max(0, available_balance),
            "total_earnings": float(total_earnings),
            "pending_balance": float(pending_balance),
            "this_month": float(this_month),
            "history": WithdrawalRequestSerializer(history, many=True).data
        })

    def post(self, request):
        seller = request.user
        serializer = WithdrawalRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            amount = float(serializer.validated_data['amount'])
            
            # Server-side validation of balance
            total_earned = OrderItem.objects.filter(
                product__seller=seller, order__status__in=['paid', 'shipped']
            ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0
            
            withdrawn = WithdrawalRequest.objects.filter(
                seller=seller, status__in=['pending', 'processing', 'completed']
            ).aggregate(t=Sum('amount'))['t'] or 0
            
            if amount > (float(total_earned) - float(withdrawn)):
                return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(seller=seller)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






class PaymentMethodView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        methods = SellerPaymentMethod.objects.filter(seller=request.user)
        serializer = PaymentMethodSerializer(methods, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PaymentMethodSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(seller=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class RequestWithdrawal(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        seller = request.user
        amount_requested = request.data.get('amount')
        method_id = request.data.get('payment_method_id')

        if not method_id:
            return Response({"error": "Payment method is required."}, status=400)

        # 1. Basic Input Validation
        try:
            amount_requested = float(amount_requested)
        except (TypeError, ValueError):
            return Response(
                {"error": "Please provide a valid numeric amount."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount_requested < 10:
            return Response(
                {"error": "Minimum withdrawal amount is  £10."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Atomic Transaction to prevent double-spending
        with transaction.atomic():
            try:
                payment_method = SellerPaymentMethod.objects.get(id=method_id, seller=seller)
            except SellerPaymentMethod.DoesNotExist:
                return Response({"error": "Invalid payment method."}, status=400)

            # Calculate Total Earned (Only from Delivered orders)
            total_earned = OrderItem.objects.filter(
                product__seller=seller, 
                order__status='pending' # fix = delivered in prod
            ).aggregate(t=Sum(F('price') * F('quantity')))['t'] or 0

            # Calculate Total already tied up in other requests (Pending, Approved, or Completed)
            total_withdrawn_or_pending = WithdrawalRequest.objects.filter(
                seller=seller, 
                status__in=['pending', 'approved', 'completed']
            ).aggregate(t=Sum('amount'))['t'] or 0
            
            # Current real-time available balance
            available_payout = float(total_earned - total_withdrawn_or_pending)

            # 3. Final Balance Check
            if amount_requested > available_payout:
                return Response({
                    "error": "Insufficient balance.",
                    "available": f" £{available_payout:,}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # 4. Ensure a Payout Method exists before allowing withdrawal
            has_payout_method = SellerPaymentMethod.objects.filter(seller=seller).exists()
            if not has_payout_method:
                return Response(
                    {"error": "Please add a payout method before requesting a withdrawal."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 5. Create the Withdrawal Request
            withdrawal = WithdrawalRequest.objects.create(
                seller=seller,
                amount=amount_requested,
                method=payment_method,
                status='pending'
            )

            return Response({
                "message": f"Withdrawal request for  £{amount_requested:,} submitted successfully.",
                "request_id": withdrawal.id,
                "remaining_balance": f"{(available_payout - amount_requested):,}"
            }, status=status.HTTP_201_CREATED)





#listings starts

class PublicListingListView(APIView):
    permission_classes = [] # Allow anyone to see the menu
    
    def get(self, request):
        # 1. Extraction
        print('request.query_params:',request.query_params)
        query = request.query_params.get('search', '')
        category_slug = request.query_params.get('category_slug', None)
        cat_id = request.query_params.get('category', '')
        page_number = request.query_params.get('page', 1)

        # 2. Filtering
        listings = Listing.objects.filter(is_active=True).order_by('-created_at')
        
        if query:
            listings = listings.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )
        
        if cat_id:
            listings = listings.filter(category_id=cat_id)

        if category_slug:
            listings = listings.filter(
                 Q(category__slug=category_slug) | Q(subcategory__slug=category_slug)
                #category__slug=category_slug
            )
            print(' listings:', listings)

        # 3. Paginating
        paginator = Paginator(listings, 12)
        page_obj = paginator.get_page(page_number)
        serializer = ListingSerializer(page_obj, many=True)

        return Response({
            "results": serializer.data,
            "pagination": {
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "total_items": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous()
            }
        })

class ListingsCategoryMenuView(APIView):
    permission_classes = [] # Allow anyone to see the menu
    
    def get(self, request):
        categories = ListingCategory.objects.prefetch_related('listingsubcategories').all()
        serializer = CategoryMenuSerializer(categories, many=True)
        return Response(serializer.data)


class ListingHomeDetailView(APIView):
    """
    Retrieves a single listing by slug and increments the view count.
    """
    permission_classes = [AllowAny]

    def get(self, request, slug):
        listing = get_object_or_404(Listing, slug=slug, is_active=True)
        
        # Increment view count on every successful fetch
        listing.views_count += 1
        listing.save(update_fields=['views_count'])
        
        serializer = ListingSerializer(listing)
        print('serializer.data:',serializer.data)
        return Response(serializer.data)

class ListingCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get(self, request):
        # 1. Get query params
        page_number = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 10) # 10 items per page

        # 2. Query and Paginate
        listings_queryset = Listing.objects.filter(seller=request.user).order_by('-created_at')
        paginator = Paginator(listings_queryset, page_size)
        
        try:
            page_obj = paginator.get_page(page_number)
            serializer = ListingSerializer(page_obj, many=True)
            print('serializer.data:',serializer.data)
            return Response({
                "results": serializer.data,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "total_items": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous()
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def post(self, request):
        # Extract files
        gallery_images = request.FILES.getlist('gallery_images')
        print('request.data:',request.data)
        
        with transaction.atomic():
            serializer = ListingSerializer(data=request.data)
            if serializer.is_valid():
                # Save listing and associate with seller
                listing = serializer.save(seller=request.user)
                
                # Bulk create gallery images
                image_objects = [
                    ListingImage(listing=listing, image=img) 
                    for img in gallery_images
                ]
                ListingImage.objects.bulk_create(image_objects)
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ListingsCategoryListView(APIView):
    """Returns categories and subcategories for the modal dropdowns"""
    def get(self, request):
        categories = ListingCategory.objects.all().prefetch_related('listingsubcategories')
        data = [
            {
                "id": cat.id,
                "name": cat.name,
                "subcategories": [{"id": sub.id, "name": sub.name} for sub in cat.listingsubcategories.all()]
            } for cat in categories
        ]
        print('data:',data)
        return Response(data)



class ListingDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    def get_object(self, slug, user):
        try:
            return Listing.objects.get(slug=slug, seller=user)
        except Listing.DoesNotExist:
            return None

    def get(self, request,slug):
        listing = self.get_object(slug, request.user)
        serializer =ListingSerializer(listing)
        print(serializer.data)
        return Response(serializer.data)

    def delete(self, request, slug):
        listing = self.get_object(slug, request.user)
        if not listing:
            return Response(status=status.HTTP_404_NOT_FOUND)
        listing.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def patch(self, request, slug):
        print('files:',request.FILES,'data:',request.data)
        listing = self.get_object(slug, request.user)
        if not listing:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ListingSerializer(listing, data=request.data, partial=True)
        if serializer.is_valid():
            images = request.FILES.getlist('additional_images') # Updated from gallery_images
            for image in images:
                ListingImage.objects.create(listing=listing, image=image)
            serializer.save()
            return Response(serializer.data)
        print('serializer.errors:',serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





class ListingsDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_listings = Listing.objects.filter(seller=user)
        
        # 1. High Level Stats
        stats = {
            "total_views": user_listings.aggregate(Sum('views_count'))['views_count__sum'] or 0,
            "active_count": user_listings.filter(is_active=True).count(),
            "total_listings": user_listings.count()
        }
        
        # 2. 7-Day View History for Chart
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)
        
        # Fetch actual data from DB
        view_data = (
            ListingView.objects.filter(listing__seller=user, date__range=[start_date, end_date])
            .values('date')
            .annotate(total=Sum('count'))
            .order_by('date')
        )
        
        # Build complete 7-day array (fill missing days with 0)
        chart_data = []
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            found = next((item for item in view_data if item['date'] == current_date), None)
            chart_data.append({
                "date": current_date.strftime('%b %d'),
                "views": found['total'] if found else 0
            })

        return Response({
            "stats": stats,
            "chart_data": chart_data
        })


class ListingImageDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        # Security: Only allow deletion if the requesting user owns the listing 
        # that this gallery image belongs to.
        image = get_object_or_404(ListingImage, pk=pk, listing__seller=request.user)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class ContactAPIView(APIView):
    permission_classes = [] # Allow anyone to contact

    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        subject = request.data.get('subject')
        message = request.data.get('message')
        print('request.data:',request.data)

        # Send Email Logic
        full_message = f"From: {name} <{email}>\n\n{message}"
        try:
            """ send_mail(
            f"Contact Form: {subject}",
            full_message,
            'noreply@mymarket.com',
            ['admin@mymarket.com'],
            fail_silently=False,
            )"""
            print('success')
            return Response({"status": "success", "message": "Email sent!"}, status=status.HTTP_200_OK)
            
        except Exception as e:
                # Log the error 'e' here in a real app
            return Response({"error": "Failed to send email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ReportListingView(APIView):
    permission_classes = [AllowAny] # Or IsAuthenticated

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk)
        
        reason = request.data.get('reason')
        details = request.data.get('details', '')
        

        ListingReport.objects.create(
            listing=listing,
            reporter=request.user if request.user.is_authenticated else None,
            reason=reason,
            details=details
        )
        
        return Response({"message": "Report submitted"}, status=201)





#password reset


class ResetPasswordRequestView(APIView):
    permission_classes = [AllowAny] # Or IsAuthenticated
    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = myuser.objects.filter(email=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            print('user:',user)
            
            # Point to your Next.js frontend route
            reset_link = f"http://localhost:3000/password-reset-confirm/{uid}/{token}/"
            print("RAW RESET LINK:", reset_link)
            
            # Context for the HTML template
            context = {'reset_link': reset_link, 'user':user}
            html_message = render_to_string('emails/password_reset.html', context)
            plain_message = strip_tags(html_message) # Fallback for old email clients

            send_mail(
                subject="Reset your DiasporaBlack password",
                message=plain_message,
                from_email="DiasporaBlack <noreply@diasporablack.com>",
                recipient_list=[email],
                html_message=html_message, # This is the crucial part
                fail_silently=False,
            )

        return Response({"detail": "If an account exists, a reset link has been sent."}, status=status.HTTP_200_OK)





class ResetPasswordConfirmView(APIView):
    permission_classes = [AllowAny] # Or IsAuthenticated
    def post(self, request):
        print('request.data:',request.data)
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
      
        
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = myuser.objects.get(id=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user and default_token_generator.check_token(user, token):
            # 1. Update the password
            user.set_password(new_password)
            user.save()

            # 2. Prepare and send the Security Alert Email
            self.send_security_alert(user)

            return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)
        
        return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

    def send_security_alert(self, user):
        context = {
            'user': user,
            'time': timezone.now()
        }
        html_message = render_to_string('emails/security_alert.html', context)
        
        send_mail(
            subject="Security Alert: DiasporaBlack Password Changed",
            message=strip_tags(html_message),
            from_email="DiasporaBlack Security <security@diasporablack.com>",
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True, # We don't want to crash the response if email fails
        )