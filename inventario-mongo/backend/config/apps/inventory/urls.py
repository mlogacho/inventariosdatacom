from django.urls import path

# =========================
# CATEGORY
# =========================
from config.apps.inventory.views.category_views import (
    CategoryListCreateView,
    CategoryDetailView,
)

# =========================
# SUBCATEGORY
# =========================
from config.apps.inventory.views.subcategory_views import (
    SubCategoryListCreateView,
    SubCategoryDetailView,
)

# =========================
# ITEMS
# =========================
from config.apps.inventory.views.item_views import (
    ItemListCreateView,
    ItemDetailView,
    ItemTransitionView,
)

# =========================
# STORE (BODEGAS)
# =========================
from config.apps.inventory.views.store_views import (
    StoreListCreateView,
    StoreDetailView,
)

# =========================
# CUSTOMER (CLIENTES)
# =========================
from config.apps.inventory.views.customer_views import (
    CustomerListCreateView,
    CustomerDetailView,
)

# =========================
# SUPPLIER (PROVEEDORES)
# =========================
from config.apps.inventory.views.supplier_views import (
    SupplierListCreateView,
    SupplierDetailView,
)

# =========================
# VEHICLE (VEHÍCULOS)
# =========================
from config.apps.inventory.views.vehicle_views import (
    VehicleListCreateView,
    VehicleDetailView,
)

# =========================
# FACILITY (INSTALACIONES)
# =========================
from config.apps.inventory.views.facility_views import (
    FacilityListCreateView,
    FacilityDetailView,
    FacilityStartView,
    FacilityFinishView,
    FacilityCancelView,
    FacilityCloseView,
    FacilityReportView,
    FacilityUpdateDestinationsView,
    FacilityMovementsView,
)

# =========================
# MOVEMENTS (TRAZABILIDAD — APPEND-ONLY)
# V-24 Fix: Agregar endpoint de historial por ítem
# =========================
from config.apps.inventory.views.movement_views import (
    MovementListCreateView,
    MovementItemHistoryView,
    MovementStatsView,
)


urlpatterns = [
    # CATEGORY
    path("categories/", CategoryListCreateView.as_view(), name="category-list-create"),
    path("categories/<str:pk>/", CategoryDetailView.as_view(), name="category-detail"),

    # SUBCATEGORY
    path("subcategories/", SubCategoryListCreateView.as_view(), name="subcategory-list-create"),
    path("subcategories/<str:pk>/", SubCategoryDetailView.as_view(), name="subcategory-detail"),

    # ITEMS
    path("items/", ItemListCreateView.as_view(), name="item-list-create"),
    path("items/<str:pk>/", ItemDetailView.as_view(), name="item-detail"),
    path("items/<str:pk>/transition/", ItemTransitionView.as_view(), name="item-transition"),

    # STORES
    path("stores/", StoreListCreateView.as_view(), name="store-list-create"),
    path("stores/<str:pk>/", StoreDetailView.as_view(), name="store-detail"),

    # CUSTOMERS
    path("customers/", CustomerListCreateView.as_view(), name="customer-list-create"),
    path("customers/<str:pk>/", CustomerDetailView.as_view(), name="customer-detail"),

    # SUPPLIERS
    path("suppliers/", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path("suppliers/<str:pk>/", SupplierDetailView.as_view(), name="supplier-detail"),

    # VEHICLES
    path("vehicles/", VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path("vehicles/<str:pk>/", VehicleDetailView.as_view(), name="vehicle-detail"),

    # FACILITIES
    path("facilities/", FacilityListCreateView.as_view(), name="facility-list-create"),
    path("facilities/<str:pk>/", FacilityDetailView.as_view(), name="facility-detail"),
    path("facilities/<str:pk>/start/", FacilityStartView.as_view(), name="facility-start"),
    path("facilities/<str:pk>/finish/", FacilityFinishView.as_view(), name="facility-finish"),
    path("facilities/<str:pk>/close/",  FacilityCloseView.as_view(),  name="facility-close"),
    path("facilities/<str:pk>/cancel/", FacilityCancelView.as_view(), name="facility-cancel"),
    path("facilities/<str:pk>/report/", FacilityReportView.as_view(), name="facility-report"),
    path("facilities/<str:pk>/destinations/", FacilityUpdateDestinationsView.as_view(), name="facility-destinations"),
    path("facilities/<str:pk>/movements/", FacilityMovementsView.as_view(), name="facility-movements"),

    # MOVEMENTS — Trazabilidad (APPEND-ONLY, sin DELETE ni UPDATE)
    # Lista global + creación
    path("movements/", MovementListCreateView.as_view(), name="movement-list-create"),
    path("movements/stats/", MovementStatsView.as_view(), name="movement-stats"),
    # V-24 Fix: Historial paginado por ítem específico
    path("movements/<str:item_id>/history/", MovementItemHistoryView.as_view(), name="movement-item-history"),
]
