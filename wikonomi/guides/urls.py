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
    path('<slug:slug>/questions/', views.question_create, name='question_create'),
    path('<slug:slug>/questions/<int:question_id>/answers/', views.answer_create, name='answer_create'),
    path('<slug:slug>/questions/<int:question_id>/answers/<int:answer_id>/accept/', views.answer_accept, name='answer_accept'),
    path('<slug:slug>/mark-delete/', views.guide_mark_delete, name='mark_delete'),
    path('<slug:slug>/veto-delete/', views.guide_veto_delete, name='veto_delete'),
    path('<slug:slug>/confirm-delete/', views.guide_confirm_delete, name='confirm_delete'),
    path('<slug:slug>/delete/', views.guide_delete, name='delete'),
    path('<slug:slug>/history/', views.guide_history, name='history'),
    path('<slug:slug>/history/<int:version_id>/', views.guide_version_detail, name='version_detail'),
    path('<slug:slug>/steps/<int:step_id>/tips/', views.tip_create, name='tip_create'),
    path('<slug:slug>/steps/<int:step_id>/tips/list/', views.tip_list, name='tip_list'),
    path('<slug:slug>/steps/tips/<int:tip_id>/edit/', views.tip_edit, name='tip_edit'),
    path('<slug:slug>/steps/tips/<int:tip_id>/vote/', views.tip_vote, name='tip_vote'),
    path('<slug:slug>/steps/tips/<int:tip_id>/delete/', views.tip_delete, name='tip_delete'),
]
