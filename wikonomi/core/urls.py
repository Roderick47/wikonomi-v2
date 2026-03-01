from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('add-price/', views.price_report_create, name='add_price'),
    path('price/<int:pk>/', views.price_report_detail, name='price_detail'),
    path('price/<int:pk>/edit/', views.edit_price_report, name='edit_price_report'),
    path('price/<int:pk>/nearby/', views.nearby_prices_detail, name='nearby_prices_detail'),
    path('business/<int:pk>/', views.business_detail, name='business_detail'),
    path('load-more/', views.load_more_prices, name='load_more_prices'),
    path('product/<int:product_id>/watch/', views.toggle_watchlist, name='toggle_watchlist'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('shopping-list/', views.shopping_lists_view, name='shopping_list'),
    path('shopping-list/add/', views.add_to_shopping_list, name='add_to_shopping_list'),
    path('shopping-list/toggle/<int:item_id>/', views.toggle_shopping_item, name='toggle_shopping_item'),
    path('shopping-list/delete/<int:item_id>/', views.delete_shopping_item, name='delete_shopping_item'),
    path('about/', views.about_view, name='about'),
]
