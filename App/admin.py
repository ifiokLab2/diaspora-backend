from django.contrib import admin
from .models import *
admin.site.register(myuser)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Listing)
#admin.site.register(ListingSubCategory)
#admin.site.register(ListingCategory)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3 # Shows 3 empty slots by default

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Categories)
class CategoriesAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}

@admin.register(ListingCategory)
class ListingCategoriesAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ListingSubCategory)
class ListingSubCategoriesAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}