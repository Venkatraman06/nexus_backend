from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    TrainingCategoryViewSet, DealViewSet, QuotationViewSet,
    public_view_quotation, public_respond_quotation
)

router = DefaultRouter()
router.register("training-categories", TrainingCategoryViewSet, basename="training-category")
router.register("deals", DealViewSet, basename="deal")
router.register("quotations", QuotationViewSet, basename="sales-quotation")

urlpatterns = [
    path("quotations/<int:pk>/view/", public_view_quotation, name="public-view-quotation"),
    path("quotations/<int:pk>/respond/", public_respond_quotation, name="public-respond-quotation"),
] + router.urls
