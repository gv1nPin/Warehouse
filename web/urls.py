from django.urls import path

from .views import api, auth, detail, draft, home, receipt, shipments

urlpatterns = [
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('employees/new/', auth.register_view, name='employee_new'),

    path('', home.home_view, name='home'),
    path('stock/', home.stock_view, name='stock'),

    path('shipments/', shipments.shipment_list_view, name='shipments'),

    path('shipments/new/', draft.draft_create_view, name='draft_new'),
    path('stages/<int:stage_id>/items/add/', draft.add_item_view, name='draft_add_item'),
    path('items/<int:item_id>/remove/', draft.remove_item_view, name='draft_remove_item'),
    path('stages/<int:stage_id>/driver/', draft.assign_driver_view, name='draft_driver'),
    path('stages/<int:stage_id>/documents/add/', draft.attach_document_view, name='draft_attach'),
    path('documents/<int:document_id>/remove/', draft.remove_document_view, name='draft_detach'),
    path('shipments/<int:shipment_id>/delete/', draft.delete_draft_view, name='draft_delete'),

    path('shipments/<int:shipment_id>/', detail.shipment_detail_view, name='shipment_detail'),
    path('stages/<int:stage_id>/reserve/', detail.reserve_view, name='stage_reserve'),
    path('stages/<int:stage_id>/ship/', detail.ship_view, name='stage_ship'),
    path('shipments/<int:shipment_id>/cancel/', detail.cancel_view, name='shipment_cancel'),
    path('stages/<int:stage_id>/documents/<int:document_id>/', detail.document_open_view, name='document_open'),

    path('receipt/', receipt.receipt_list_view, name='receipt'),
    path('stages/<int:stage_id>/facts/', receipt.save_facts_view, name='receipt_facts'),
    path('stages/<int:stage_id>/accept/', receipt.accept_view, name='receipt_accept'),

    path('api/auth/login/', api.LoginView.as_view(), name='api_login'),
    path('api/stock/', api.StockListView.as_view(), name='api_stock'),
    path('api/shipments/draft/', api.CreateDraftView.as_view(), name='api_draft_create'),
    path('api/stages/<int:stage_id>/ship/', api.ShipStageView.as_view(), name='api_stage_ship'),
    path('api/stages/<int:stage_id>/accept/', api.AcceptStageView.as_view(), name='api_stage_accept'),
    path('api/shipments/<int:shipment_id>/cancel/', api.CancelShipmentView.as_view(), name='api_shipment_cancel'),
]
