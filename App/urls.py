from django.urls import path
from .views import *
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('listings/categories/menu/', ListingsCategoryMenuView.as_view(), name='listings-cat-list'),
    path('listings/home/', PublicListingListView.as_view(), name='listings-home-list'),
    path('listings/public/<str:slug>/', ListingHomeDetailView.as_view(), name='listings-detail-list'),
    path('listings/categories/', ListingsCategoryListView.as_view(), name='listings-category-list'),
    path('products-manage/', ProductListCreateAPIView.as_view(), name='product-manage'),
    path('products-categories/', CategoryListAPIView.as_view(), name='category-list'),
    path('orders/', OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:id>/', OrderDetailView.as_view(), name='order-detail'),
    path('stripe-webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    #path('', ProductListView.as_view(), name='product-list'),
    path('products/category/', ProductCategoryListView.as_view(), name='product-list-cat'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('saved-items/', SavedItemsListView.as_view(), name='saved-items-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('search/products/', ProductSearchListView.as_view(), name='search-product-list'),
    path('search/listings/', ListingsSearchListView.as_view(), name='search-listings'),
    path('products/suggestions/', ProductSuggestionView.as_view(), name='product-suggestions'),
    path('products/<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/saved/toggle/<int:product_id>/', ToggleSavedItemView.as_view(), name='ToggleSavedItemView'), # Full removal
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('update/', UpdateCartQuantityView.as_view(), name='cart-update'), # Handles + and -
    path('remove/<int:product_id>/', RemoveFromCartView.as_view(), name='cart-remove'), # Full removal
    
    
    path('auth/customer/login/', CustomerLoginView.as_view()),
    path('auth/seller/login/', SellerLoginView.as_view()),
    path('auth/customer/register/', CustomerRegisterView.as_view(), name='customer-register'),
    path('auth/seller/register/', SellerRegisterView.as_view(), name='seller-register'),
    path('auth/users/me/', UserMeView.as_view(), name='user-me'),
    # Location data for the dropdowns
    path('locations/', LocationDataView.as_view(), name='location-list'),
    path('listings/locations/cities/', ListingCitySearchAPIView.as_view(), name='llistings-location-list'),

    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/clear/', ClearCartView.as_view(), name='clear-cart'),
    path('cart/add/', AddToCartView.as_view(), name='cart-add'),
    path('cart/remove/<int:product_id>/', RemoveFromCartView.as_view(), name='cart-remove'),
    path('cart/update/', UpdateCartQuantityView.as_view(), name='cart-update'),
    #seller

    path('sellers/profile/create/', CreateShopProfileAPIView.as_view(), name='create-profile'),
    path('sellers/profile/me/', GetShopProfileAPIView.as_view(), name='get-profile'),
    path('sellers/profile/update/', ShopProfileUpdateAPIView.as_view(), name='shop-profile-update'),
    path('seller/orders/', SellerOrderListView.as_view(), name='seller-orders'),
    path('seller/analytics/', SellerAnalyticsView.as_view(), name='seller-analytics'),
    path('seller/dashboard/', SellerDashboardAnalytics.as_view(), name='seller-dashboard'),
    path('seller/payouts/', SellerPayoutView.as_view(), name='seller-payouts'),
    # Payment Methods Management
    path('seller/payment-methods/', PaymentMethodView.as_view(), name='seller-payment-methods'),
    path('seller/withdraw/', RequestWithdrawal.as_view(), name='seller-withdraw'), # Add this line



    #listings
    path('listings/dashboard-analytics/', ListingsDashboardAPIView.as_view(), name='dashboard-analytics'),
    path('listings/', ListingCreateView.as_view(), name='listing-create'),
    path('listings/<str:slug>/', ListingDetailView.as_view(), name='listing-detail'),
    path('listings/images/<int:pk>/', ListingImageDeleteAPIView.as_view(), name='listing-image-delete'),
    #path('listings/my-listings/', MyListingsAPIView.as_view(), name='my-listings'),
    path('contact-us/', ContactAPIView.as_view(), name='contact-us'),
    path('listings/<int:pk>/report/', ReportListingView.as_view(), name='report-listings'),

    path('auth/users/reset_password/', ResetPasswordRequestView.as_view(), name='reset_password'),
    
    # Matches api.post('/auth/users/reset_password_confirm/')
    path('auth/users/reset_password_confirm/', ResetPasswordConfirmView.as_view(), name='reset_password_confirm'),
    
    
    # Fetch categories for the form dropdowns
   

]