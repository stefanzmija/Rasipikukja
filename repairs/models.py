from django.contrib import admin
from django.contrib.auth.models import User
from django.db import models
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm
from django import forms


# Model for Repairman Categories
class RepairCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# Model for Repairmen
class Repairman(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    category = models.ForeignKey(RepairCategory, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.user.username


# Model for Jobs
class Job(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(RepairCategory, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# Register models in the admin panel
admin.site.register(RepairCategory)
admin.site.register(Repairman)
admin.site.register(Job)


# Forms
class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'description', 'category']


# Views for user authentication
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


# Views for displaying jobs and repairmen
def home_view(request):
    jobs = Job.objects.all()
    return render(request, 'home.html', {'jobs': jobs})


def repairmen_view(request):
    repairmen = Repairman.objects.all()
    return render(request, 'repairmen.html', {'repairmen': repairmen})


def add_job_view(request):
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = JobForm()
    return render(request, 'add_job.html', {'form': form})


# URL patterns
urlpatterns = [
    path('', home_view, name='home'),
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('repairmen/', repairmen_view, name='repairmen'),
    path('add-job/', add_job_view, name='add_job'),
]
