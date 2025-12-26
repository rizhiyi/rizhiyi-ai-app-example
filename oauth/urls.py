from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('demo/', views.demo_flow, name='demo_flow'),
    path('callback/', views.callback, name='callback'),
    path('logout/', views.logout, name='logout'),
    path('save_api_key/', views.save_api_key, name='save_api_key'),
    path('crewai/', views.crewai_demo, name='crewai_demo'),
    path('crewai/run/', views.crewai_run, name='crewai_run'),
    path('crewai/status/<str:run_id>/', views.crewai_status, name='crewai_status'),
    path('crewai/input/<str:run_id>/', views.crewai_input, name='crewai_input'),
    path('crewai/stop/<str:run_id>/', views.crewai_stop, name='crewai_stop'),
    path('crewai/history/', views.crewai_history, name='crewai_history'),
    path('crewai/sessions/', views.crewai_sessions, name='crewai_sessions'),
    path('crewai/new_session/', views.crewai_new_session, name='crewai_new_session'),
    path('crewai/delete_session/<int:session_id>/', views.crewai_delete_session, name='crewai_delete_session'),
    path('mcp/list/', views.mcp_list, name='mcp_list'),
    path('csv_manager/', views.csv_manager, name='csv_manager'),
]