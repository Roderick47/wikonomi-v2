from django.urls import path

from . import views

app_name = 'promotions'

urlpatterns = [
    path('', views.promotion_list, name='list'),
    path('report/', views.promotion_create, name='create'),
    path('<int:pk>/', views.promotion_detail, name='detail'),
    path('<int:pk>/confirm/', views.confirm_promotion, name='confirm'),
]
