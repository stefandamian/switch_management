from django.contrib import admin
from django.urls import path, include
from . import views

app_name='switches'

urlpatterns = [
    path(r'', views.index, name='index'),
    path(r'<int:Switch_id>/', views.detail, name='detail'),
    path(r'add',views.add_switch, name='add_switch'),
    path(r'<int:Switch_id>/delete',views.delete_switch, name='delete_switch'), 
    path(r'<int:Switch_id>/edit',views.edit_switch, name='edit_switch'),
    path(r'deleted<int:Switch_id>', views.del_switch_confirmed, name='del_switch_confirmed'),
    path(r'<int:Switch_id>/ref', views.data_refresh, name="data_refresh"),
    path(r'<int:Switch_id>/change_port_state', views.change_port_state, name="change_port_state"),
    path(r'<int:Switch_id>/add_vlan', views.add_vlan, name="add_vlan"),
    path(r'<int:Switch_id>/edit_vlan/<int:VID>', views.edit_vlan, name="edit_vlan"),
    path(r'<int:Switch_id>/del_vlan/<int:VID>', views.delete_vlan, name="delete_vlan"),
    path(r'<int:Switch_id>/port_no_vlan',views.port_vlan_remove, name="port_vlan_remove"),
    path(r'<int:Switch_id>/<int:VID>/add_port',views.add_port_vlan, name="add_port_vlan"),
    path(r'<int:Switch_id>/cpu_monitor',views.monitoring_cpu, name="monitoring_cpu"),
    path(r'<int:Switch_id>/cpu_monitor/get_data',views.get_json, name="get_json")
]
