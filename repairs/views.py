from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from .supabase_client import supabase
import shutil
from django.http import HttpResponse
import uuid
import time
import tempfile
import os
User = get_user_model()

def home_view(request):
    services = [
        {"name": "Cleaner", "icon_url": "/static/icons/cleaning.png"},
        {"name": "Handyman", "icon_url": "/static/icons/handyman.png"},
        {"name": "Mover", "icon_url": "/static/icons/moving.png"},
        {"name": "Painter", "icon_url": "/static/icons/painting.png"},
        {"name": "Plumber", "icon_url": "/static/icons/plumbing.png"},
        {"name": "Electrician", "icon_url": "/static/icons/electrical.png"},
        {"name": "Assembler", "icon_url": "/static/icons/assembly.png"},
        {"name": "Gardener", "icon_url": "/static/icons/gardening.png"},
    ]
    return render(request, "home.html", {"services": services})

def custom_signup_view(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            user_type = request.POST.get('user_type')
            repair_category = request.POST.get('repair_category') if user_type == 'repairman' else None

            if not name or not email or not password or not user_type:
                messages.error(request, "All fields are required.")
                return redirect('signup')

            if user_type not in ['client', 'repairman']:
                messages.error(request, "Invalid user type.")
                return redirect('signup')

            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })

            if auth_response.user:
                profile_data = {
                    "email": email,
                    "name": name,
                    "user_type": user_type,
                }
                if user_type == 'repairman':
                    if not repair_category:
                        messages.error(request, "Repair category is required for repairmen.")
                        return redirect('signup')
                    profile_data["repair_category"] = repair_category
                    profile_data["rating"] = 0

                insert_response = supabase.table("profiles").insert(profile_data).execute()
                print("Profile insert response:", insert_response)

                messages.success(request, "Registration successful. Please log in.")
                return redirect('login')
            else:
                error_msg = getattr(auth_response, 'error', 'Unknown error')
                messages.error(request, f"Sign-up failed: {error_msg}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    return render(request, 'signup.html')

def custom_login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if auth_response.session:
            token = auth_response.session.access_token
            request.session['supabase_token'] = token

            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)

            profile_response = supabase.table("profiles").select("user_type").eq("email", email).execute()
            if profile_response.data:
                request.session['user_type'] = profile_response.data[0]['user_type']
            else:
                request.session['user_type'] = "client"
            messages.success(request, "Logged in successfully!")
            return redirect('home')
        else:
            messages.error(request, "Login failed. Please check your credentials.")
    return render(request, 'login.html')

def custom_logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')

def repairmen_view(request, category=None):
    """
    Displays a list of repairmen. If 'category' is provided, filters by that category.
    If 'search' is provided in GET, filters by name or email with more precise matching.
    Passes 'user_type' into the template so only clients see the rate button.
    """
    # Get the search query from the GET parameters
    search_query = request.GET.get('search', '').strip().lower()

    # Initial query for all repairmen
    response = supabase.table("profiles").select("*").eq("user_type", "repairman").execute()
    repairmen = response.data if response.data else []

    # Apply category filter if provided
    if category:
        repairmen = [r for r in repairmen if r.get('repair_category', '').lower() == category.lower()]

    # Apply search filter if a query exists
    if search_query:
        repairmen = [r for r in repairmen if
                     any(word.lower() == search_query for word in (r.get('name', '').lower() or '').split()) or
                     search_query in (r.get('email', '').lower() or '')]

    # Get user_type from session (defaulting to 'client')
    user_type = request.session.get('user_type', 'client')
    return render(request, "repairmen.html", {
        "repairmen": repairmen,
        "selected_category": category,
        "user_type": user_type,
    })

def rate_repairman_view(request, repairman_email):
    if request.method == "POST":
        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "")

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                messages.error(request, "Invalid rating. Please select a value between 1 and 5.")
                return redirect("rate_repairman", repairman_email=repairman_email)
        except ValueError:
            messages.error(request, "Invalid rating format.")
            return redirect("rate_repairman", repairman_email=repairman_email)

        response = supabase.table("reviews").insert({
            "repairman_email": repairman_email,
            "client_email": request.user.email,
            "rating": rating,
            "comment": comment,
        }).execute()

        response_error = getattr(response, "error", None)
        if response_error is None:
            messages.success(request, "Review submitted successfully!")
            return redirect("repairman_profile", repairman_email=repairman_email)
        else:
            messages.error(request, "Failed to submit review. Please try again.")
            print("Insert error:", response_error)
            return redirect("rate_repairman", repairman_email=repairman_email)

    return render(request, "rate_repairman.html", {"repairman_email": repairman_email})

def repairman_profile_view(request, repairman_email):
    profile_response = supabase.table("profiles").select("*").eq("email", repairman_email).execute()
    profile = profile_response.data[0] if profile_response.data else None
    if not profile:
        messages.error(request, "Repairman not found.")
        return redirect("repairmen_all")
    reviews_response = supabase.table("reviews").select("*").eq("repairman_email", repairman_email).execute()
    reviews = reviews_response.data if reviews_response.data else []
    context = {
        "profile": profile,
        "reviews": reviews,
    }
    return render(request, "repairman_profile.html", context)

def my_profile_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view your profile.")
        return redirect('login')
    email = request.user.email
    profile_response = supabase.table("profiles").select("*").eq("email", email).execute()
    profile = profile_response.data[0] if profile_response.data else {}
    if request.method == "POST":
        contact = request.POST.get("contact")
        description = request.POST.get("description")
        update_data = {
            "contact": contact,
            "description": description,
        }
        update_response = supabase.table("profiles").update(update_data).eq("email", email).execute()
        print("Profile update response:", update_response)
        profile_response = supabase.table("profiles").select("*").eq("email", email).execute()
        profile = profile_response.data[0] if profile_response.data else {}
        messages.success(request, "Profile updated successfully!")
        return redirect('my_profile')
    context = {"profile": profile}
    return render(request, "my_profile.html", context)
def add_problem_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to add a problem.")
        return redirect("login")

    if request.session.get("user_type", "client") != "client":
        messages.error(request, "Only clients can add problems.")
        return redirect("home")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        contact = request.POST.get("contact", "").strip()
        location = request.POST.get("location", "").strip()
        caption = request.POST.get("caption", "").strip()  # New caption field
        description = request.POST.get("description", "").strip()
        category = request.POST.get("category", "").strip()
        client_email = request.user.email

        if not all([name, contact, location, caption, category]):  # Include caption in validation
            messages.error(request, "All fields except description and photo are required.")
            return redirect("add_problem")

        photo_url = ""
        if "photo" in request.FILES:
            photo_file = request.FILES["photo"]
            if not photo_file.name.lower().endswith(".png"):
                messages.error(request, "Only PNG files are allowed for the photo.")
                return redirect("add_problem")

            file_name = f"problem_{int(time.time())}_{photo_file.name}"
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    shutil.copyfileobj(photo_file.file, tmp)
                    tmp_path = tmp.name
            except Exception as e:
                messages.error(request, f"Error saving file locally: {str(e)}")
                return redirect("add_problem")

            try:
                with open(tmp_path, "rb") as f:
                    upload_response = supabase.storage.from_("problem-photos").upload(
                        file_name, f, file_options={"content-type": "image/png"}
                    )
                if hasattr(upload_response, "status_code") and upload_response.status_code not in [200, 201]:
                    raise Exception(f"Upload failed with status {upload_response.status_code}")
            except Exception as e:
                os.remove(tmp_path)
                messages.error(request, f"Error uploading file to Supabase: {str(e)}")
                return redirect("add_problem")

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            try:
                photo_url = supabase.storage.from_("problem-photos").get_public_url(file_name)
                if not isinstance(photo_url, str) or not photo_url.startswith("http"):
                    raise Exception("Invalid URL returned")
            except Exception as e:
                messages.error(request, f"Error retrieving public URL: {str(e)}")
                return redirect("add_problem")

        problem_data = {
            "client_email": client_email,
            "name": name,
            "contact": contact,
            "location": location,
            "caption": caption,  # Add caption to problem data
            "description": description if description else None,
            "photo_url": photo_url if photo_url else None,
            "category": category,
        }

        try:
            insert_response = supabase.table("problems").insert(problem_data).execute()
            if not insert_response.data:
                raise Exception("Insert returned no data - possible schema mismatch or server error")
            messages.success(request, "Your problem has been submitted successfully!")
            return redirect("home")
        except Exception as e:
            messages.error(request, f"Error submitting problem: {str(e)}")
            return redirect("add_problem")

    categories = [
        "Cleaner", "Handyman", "Mover", "Painter", "Plumber", "Electrician", "Assembler", "Gardener"
    ]
    return render(request, "add_problem.html", {"categories": categories})

def available_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view available problems.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can view available problems.")
        return redirect("home")

    # Get the search query from the GET parameters
    search_query = request.GET.get('search', '').strip().lower()

    # Fetch all problems
    problems_response = supabase.table("problems").select("*").order("created_at", desc=False).execute()
    problems = problems_response.data if problems_response.data else []

    # Apply search filter if a query exists (search in description)
    if search_query:
        problems = [p for p in problems if
                    any(word.lower() == search_query for word in (p.get('description', '').lower() or '').split())]

    # Hide contact information for repairmen
    for problem in problems:
        problem.pop('contact', None)

    return render(request, "available_problems.html", {"problems": problems})

def problem_detail_view(request, problem_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view problem details.")
        return redirect("login")
    if request.session.get('user_type', 'client') not in ['client', 'repairman']:
        messages.error(request, "Only clients and repairmen can view problem details.")
        return redirect("home")

    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    if not problem_response.data:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")

    problem = problem_response.data[0]

    bids_response = supabase.table("bids").select("*").eq("problem_id", problem_id).execute()
    bids = bids_response.data if bids_response.data else []

    assigned_response = supabase.table("assigned_problems").select("repairman_email").eq("problem_id", problem_id).execute()
    assigned_repairman = assigned_response.data[0]["repairman_email"] if assigned_response.data else None

    return render(request, "problem_detail.html", {
        "problem": problem,
        "bids": bids,
        "assigned_repairman": assigned_repairman,
    })

def submit_bid_view(request, problem_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to submit a bid.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can submit bids.")
        return redirect("home")

    if request.method == "POST":
        amount = request.POST.get("amount")
        repairman_email = request.user.email

        bid_data = {
            "problem_id": problem_id,
            "repairman_email": repairman_email,
            "amount": amount,
        }
        insert_response = supabase.table("bids").insert(bid_data).execute()
        print("Bid insert response:", insert_response)

        messages.success(request, "Your bid has been submitted successfully!")
        return redirect("available_problems")

    return render(request, "submit_bid.html", {"problem_id": problem_id})

def select_repairman_view(request, problem_id, repairman_email):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to select a repairman.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'client':
        messages.error(request, "Only clients can select repairmen.")
        return redirect("home")

    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    if not problem_response.data:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")

    problem = problem_response.data[0]

    assigned_problem_data = {
        "problem_id": problem_id,
        "client_email": problem["client_email"],
        "repairman_email": repairman_email,
        "status": "pending",
    }
    try:
        insert_response = supabase.table("assigned_problems").insert(assigned_problem_data).execute()
        print("Assigned problem insert response:", insert_response)
    except Exception as e:
        messages.error(request, f"Error assigning problem: {str(e)}")
        return redirect("available_problems")

    try:
        delete_response = supabase.table("problems").delete().eq("id", problem_id).execute()
        print("Problem delete response:", delete_response)
    except Exception as e:
        messages.error(request, f"Error deleting problem: {str(e)}")
        return redirect("available_problems")

    messages.success(request, "Repairman selected successfully!")
    return redirect("my_profile")

def pending_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view pending problems.")
        return redirect("login")

    user_email = request.user.email
    user_type = request.session.get('user_type', 'client')

    if user_type == 'client':
        response = supabase.table("assigned_problems").select("*").eq("client_email", user_email).execute()
    else:
        response = supabase.table("assigned_problems").select("*").eq("repairman_email", user_email).execute()

    pending_problems = response.data if response.data else []
    return render(request, "pending_problems.html", {"pending_problems": pending_problems})

def my_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view your problems.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'client':
        messages.error(request, "Only clients can view their problems.")
        return redirect("home")

    client_email = request.user.email
    problems_response = supabase.table("problems").select("*").eq("client_email", client_email).execute()
    problems = problems_response.data if problems_response.data else []

    return render(request, "my_problems.html", {"problems": problems})

def my_assigned_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view your assigned problems.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can view their assigned problems.")
        return redirect("home")

    repairman_email = request.user.email
    assigned_response = supabase.table("assigned_problems").select("*").eq("repairman_email", repairman_email).execute()
    assigned_problems = assigned_response.data if assigned_response.data else []

    for problem in assigned_problems:
        problem_id = problem["problem_id"]
        problem_details_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
        if problem_details_response.data:
            problem.update(problem_details_response.data[0])

    return render(request, "my_assigned_problems.html", {"assigned_problems": assigned_problems})