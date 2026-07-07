from django.urls import path

from . import views

app_name = 'guides'

urlpatterns = [
    path('', views.guide_list, name='list'),
    path('new/', views.guide_create, name='create'),
    path('<slug:slug>/', views.guide_detail, name='detail'),
    path('<slug:slug>/edit/', views.guide_edit, name='edit'),
    path('<slug:slug>/fork/', views.guide_fork, name='fork'),
    path('<slug:slug>/rate/', views.guide_rate, name='rate'),
    path('<slug:slug>/history/', views.guide_history, name='history'),
    path('<slug:slug>/history/<int:version_id>/', views.guide_version_detail, name='version_detail'),
    path('<slug:slug>/steps/<int:step_id>/tips/', views.tip_create, name='tip_create'),
    path('<slug:slug>/steps/tips/<int:tip_id>/vote/', views.tip_vote, name='tip_vote'),
]
