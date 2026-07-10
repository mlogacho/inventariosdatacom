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
from config.apps.inventory.views.crm_customer_views import CRMActiveCustomerListView, CRMActiveUserListView

# =========================
# MOVEMENTS (TRAZABILIDAD — APPEND-ONLY)
# V-24 Fix: Agregar endpoint de historial por ítem
# =========================
from config.apps.inventory.views.movement_views import (
    MovementListCreateView,
    MovementItemHistoryView,
    MovementStatsView,
    MovementActaEntregaRecepcionView,
)

from config.apps.inventory.views.kardex_views import KardexDashboardView

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
    path("crm/customers/", CRMActiveCustomerListView.as_view(), name="crm-active-customers"),
    path("crm/users/", CRMActiveUserListView.as_view(), name="crm-active-users"),

    # MOVEMENTS — Trazabilidad (APPEND-ONLY, sin DELETE ni UPDATE)
    # Lista global + creación
    path("movements/", MovementListCreateView.as_view(), name="movement-list-create"),
    path("movements/stats/", MovementStatsView.as_view(), name="movement-stats"),
    path(
        "movements/acta-entrega-recepcion/",
        MovementActaEntregaRecepcionView.as_view(),
        name="movement-acta-entrega-recepcion",
    ),
    # V-24 Fix: Historial paginado por ítem específico
    path("movements/<str:item_id>/history/", MovementItemHistoryView.as_view(), name="movement-item-history"),

    path("kardex/", KardexDashboardView.as_view(), name="kardex-dashboard"),
]
