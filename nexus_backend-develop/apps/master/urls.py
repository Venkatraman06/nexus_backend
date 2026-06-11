from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DesignationViewSet, DepartmentViewSet, LocationViewSet,
    GradeViewSet, EmploymentTypeViewSet, ShiftCategoryViewSet, RateCardViewSet,
    DesignationDropdownView, DepartmentDropdownView, LocationDropdownView,
    GradeDropdownView, EmploymentTypeDropdownView, ShiftCategoryDropdownView,
    ClientCategoryViewSet, ClientCategoryDropdownView,
    BusinessTypeViewSet, BusinessTypeDropdownView,
    BillingTypeViewSet, BillingTypeDropdownView,
)

router = DefaultRouter()
router.register("master/designations",       DesignationViewSet,    basename="designation")
router.register("master/departments",        DepartmentViewSet,     basename="department")
router.register("master/locations",          LocationViewSet,       basename="location")
router.register("master/grades",             GradeViewSet,          basename="grade")
router.register("master/employment-types",   EmploymentTypeViewSet, basename="employment-type")
router.register("master/shift-categories",  ShiftCategoryViewSet,  basename="shift-category")
router.register("master/rate-cards",        RateCardViewSet,       basename="rate-card")
router.register("master/client-categories", ClientCategoryViewSet, basename="client-category")
router.register("master/business-types",    BusinessTypeViewSet,   basename="business-type")
router.register("master/billing-types",     BillingTypeViewSet,    basename="billing-type")

urlpatterns = router.urls + [
    path("master/dropdown/designations/",       DesignationDropdownView.as_view(),    name="dropdown-designations"),
    path("master/dropdown/departments/",        DepartmentDropdownView.as_view(),     name="dropdown-departments"),
    path("master/dropdown/locations/",          LocationDropdownView.as_view(),       name="dropdown-locations"),
    path("master/dropdown/grades/",             GradeDropdownView.as_view(),          name="dropdown-grades"),
    path("master/dropdown/employment-types/",   EmploymentTypeDropdownView.as_view(), name="dropdown-employment-types"),
    path("master/dropdown/shift-categories/",   ShiftCategoryDropdownView.as_view(),  name="dropdown-shift-categories"),
    path("master/dropdown/client-categories/",  ClientCategoryDropdownView.as_view(), name="dropdown-client-categories"),
    path("master/dropdown/business-types/",     BusinessTypeDropdownView.as_view(),   name="dropdown-business-types"),
    path("master/dropdown/billing-types/",      BillingTypeDropdownView.as_view(),    name="dropdown-billing-types"),
]
