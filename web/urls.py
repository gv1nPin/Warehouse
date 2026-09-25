"""
URL-маршруты кабинета склада.

Страницы (HTML) — server-side render вместо SPA index.html.
API (JSON) — для автотестов / будущих клиентов.
"""
from django.urls import path

from . import views_pages as views

app_name = "cabinet"

urlpatterns = [
    # --- страницы ---
    path("login/", views.LoginPageView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("", views.HomePageView.as_view(), name="home"),
    path("shipments/", views.ShipmentListPageView.as_view(), name="shipment_list"),
    path("trips/", views.ShipmentListPageView.as_view(trips_only=True), name="trips"),
    path("shipments/new/", views.ShipmentCreatePageView.as_view(), name="shipment_create"),
    path("shipments/<int:shipment_id>/", views.ShipmentDetailPageView.as_view(), name="shipment_detail"),
    path("receipt/", views.ReceiptPageView.as_view(), name="receipt"),
    path("stock/", views.StockPageView.as_view(), name="stock"),
    path("docs/", views.DocsPageView.as_view(), name="docs"),
    path("employees/", views.EmployeesPageView.as_view(), name="employees"),
    path("employees/register/", views.EmployeeRegisterPageView.as_view(), name="employee_register"),
    path("employees/<int:employee_id>/toggle/", views.EmployeeToggleView.as_view(), name="employee_toggle"),
    path("refs/", views.RefsPageView.as_view(), name="refs"),

    # --- POST-действия (формы со страниц) ---
    path("stages/<int:stage_id>/reserve/", views.StageReserveView.as_view(), name="stage_reserve"),
    path("stages/<int:stage_id>/ship/", views.StageShipView.as_view(), name="stage_ship"),
    path("stages/<int:stage_id>/accept/", views.StageAcceptView.as_view(), name="stage_accept"),
    path("stages/<int:stage_id>/attach/", views.StageAttachDocView.as_view(), name="stage_attach_doc"),
    path("documents/<int:document_id>/remove/", views.StageRemoveDocView.as_view(), name="stage_remove_doc"),
    path("shipments/<int:shipment_id>/cancel/", views.ShipmentCancelView.as_view(), name="shipment_cancel"),
    path("shipments/<int:shipment_id>/delete/", views.ShipmentDeleteView.as_view(), name="shipment_delete"),

    # --- JSON API (совместимость с прежним config/urls) ---
    path("api/auth/login/", views.LoginAPIView.as_view(), name="api_login"),
    path("api/stock/", views.StockListAPIView.as_view(), name="api_stock"),
    path("api/shipments/draft/", views.CreateDraftAPIView.as_view(), name="api_create_draft"),
    path("api/stages/<int:stage_id>/ship/", views.ShipStageAPIView.as_view(), name="api_ship_stage"),
    path("api/stages/<int:stage_id>/accept/", views.AcceptStageAPIView.as_view(), name="api_accept_stage"),
    path("api/shipments/<int:shipment_id>/cancel/", views.CancelShipmentAPIView.as_view(), name="api_cancel_shipment"),
]
