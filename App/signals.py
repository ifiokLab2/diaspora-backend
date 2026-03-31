import cloudinary.uploader
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import *

@receiver(post_delete, sender=Product)
def auto_delete_cloudinary_main_image(sender, instance, **kwargs):
    # .public_id is the unique identifier Cloudinary needs to delete the file
    if instance.main_image:
        try:
            cloudinary.uploader.destroy(instance.main_image.public_id)
        except Exception as e:
            print(f"Error deleting Cloudinary asset: {e}")

@receiver(post_delete, sender=ProductImage)
def auto_delete_cloudinary_gallery_image(sender, instance, **kwargs):
    if instance.image:
        try:
            cloudinary.uploader.destroy(instance.image.public_id)
        except Exception as e:
            print(f"Error deleting Cloudinary asset: {e}")


@receiver(post_delete, sender=Listing)
def delete_listing_main_image(sender, instance, **kwargs):
    if instance.main_image:
        cloudinary.uploader.destroy(instance.main_image.public_id)

@receiver(post_delete, sender=ListingImage)
def delete_listing_gallery_image(sender, instance, **kwargs):
    if instance.image:
        cloudinary.uploader.destroy(instance.image.public_id)