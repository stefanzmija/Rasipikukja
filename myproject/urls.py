from django.contrib import admin
from django.urls import path
from repairs.views import (
    home_view,
    custom_signup_view,
    custom_login_view,
    custom_logout_view,
    repairmen_view,
    rate_repairman_view,
    repairman_profile_view,
    my_profile_view,
    add_problem_view,
    available_problems_view,
    problem_detail_view,
    submit_bid_view,
    select_repairman_view,
    pending_problems_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('signup/', custom_signup_view, name='signup'),
    path('login/', custom_login_view, name='login'),
    path('logout/', custom_logout_view, name='logout'),
    path('repairmen/', repairmen_view, name='repairmen_all'),
    path('repairmen/<str:category>/', repairmen_view, name='repairmen_by_category'),
path('rate/<str:repairman_email>/', rate_repairman_view, name='rate_repairman'),

    path('repairman/<str:repairman_email>/', repairman_profile_view, name='repairman_profile'),
    path('myprofile/', my_profile_view, name='my_profile'),
    path('add-problem/', add_problem_view, name='add_problem'),
    path('available-problems/', available_problems_view, name='available_problems'),
    path("problem/<int:problem_id>/", problem_detail_view, name="problem_detail"),
    path('submit-bid/<int:problem_id>/', submit_bid_view, name='submit_bid'),
    path('select-repairman/<int:problem_id>/', select_repairman_view, name='select_repairman'),
    path('pending-problems/', pending_problems_view, name='pending_problems'),
]