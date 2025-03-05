import os
import time
import tempfile
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login, logout
from .supabase_client import supabase
import shutil


from django.contrib.auth import get_user_model

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
            # Retrieve form data
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            user_type = request.POST.get('user_type')  # 'client' or 'repairman'
            repair_category = request.POST.get('repair_category') if user_type == 'repairman' else None

            # Validate required fields
            if not name or not email or not password or not user_type:
                messages.error(request, "All fields are required.")
                return redirect('signup')

            # Validate user_type
            if user_type not in ['client', 'repairman']:
                messages.error(request, "Invalid user type.")
                return redirect('signup')

            # Sign up the user in Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })

            if auth_response.user:
                # Build profile data for insertion into the 'profiles' table
                profile_data = {
                    "email": email,
                    "name": name,
                    "user_type": user_type,
                }

                # Add repair_category only if the user is a repairman
                if user_type == 'repairman':
                    if not repair_category:
                        messages.error(request, "Repair category is required for repairmen.")
                        return redirect('signup')
                    profile_data["repair_category"] = repair_category
                    profile_data["rating"] = 0  # Initialize rating for repairmen

                # Insert profile data into Supabase
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

            # Fetch the user's profile to retrieve user_type.
            profile_response = supabase.table("profiles").select("user_type").eq("email", email).execute()
            if profile_response.data:
                request.session['user_type'] = profile_response.data[0]['user_type']
            else:
                request.session['user_type'] = "client"  # Default fallback.
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
    Passes 'user_type' into the template so only clients see the rate button.
    """
    if category:
        response = supabase.table("profiles").select("*") \
            .eq("user_type", "repairman") \
            .eq("repair_category", category).execute()
    else:
        response = supabase.table("profiles").select("*") \
            .eq("user_type", "repairman").execute()
    repairmen = response.data if response.data else []
    # Get user_type from session (defaulting to 'client')
    user_type = request.session.get('user_type', 'client')
    return render(request, "repairmen.html", {
        "repairmen": repairmen,
        "selected_category": category,
        "user_type": user_type,
    })

def rate_repairman_view(request, repairman_email):
    # Ensure the user is logged in.
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to rate a repairman.")
        return redirect("login")
    client_email = request.user.email

    # Fetch client profile.
    client_profile_response = supabase.table("profiles").select("*").eq("email", client_email).execute()
    if not client_profile_response.data:
        messages.error(request, "Your profile was not found. Please contact support.")
        return redirect("repairmen_all")
    client_profile = client_profile_response.data[0]
    if client_profile.get("user_type") != "client":
        messages.error(request, "Only clients can rate repairmen.")
        return redirect("repairmen_all")
    if client_email == repairman_email:
        messages.error(request, "You cannot rate yourself.")
        return redirect("repairmen_all")
    existing_rating_response = supabase.table("reviews").select("*")\
        .eq("repairman_email", repairman_email)\
        .eq("client_email", client_email).execute()
    if existing_rating_response.data:
        messages.error(request, "You have already rated this repairman.")
        return redirect("repairmen_all")
    if request.method == "POST":
        rating_str = request.POST.get("rating", "0")
        comment = request.POST.get("comment", "")
        try:
            rating = int(rating_str)
        except ValueError:
            rating = 0
        review_data = {
            "repairman_email": repairman_email,
            "client_email": client_email,
            "rating": rating,
            "comment": comment,
        }
        review_response = supabase.table("reviews").insert(review_data).execute()
        print("Review insert response:", review_response)
        reviews_response = supabase.table("reviews").select("rating")\
            .eq("repairman_email", repairman_email).execute()
        reviews = reviews_response.data if reviews_response.data else []
        if reviews:
            total_rating = sum(int(r["rating"]) for r in reviews)
            avg_rating = total_rating / len(reviews)
        else:
            avg_rating = 0.0
        avg_rating = round(avg_rating, 1)
        if avg_rating > 5.0:
            avg_rating = 5.0
        update_response = supabase.table("profiles").update({"rating": avg_rating})\
            .eq("email", repairman_email).execute()
        print("Profile update response:", update_response)
        messages.success(request, "Thank you for your review!")
        return redirect("repairmen_all")
    else:
        context = {"repairman_email": repairman_email}
        return render(request, "rate_repairman.html", context)

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
    # Ensure user is logged in
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to add a problem.")
        return redirect("login")

    # Only allow clients to add problems
    if request.session.get("user_type", "client") != "client":
        messages.error(request, "Only clients can add problems.")
        return redirect("home")

    if request.method == "POST":
        # Retrieve and validate form data
        name = request.POST.get("name", "").strip()
        contact = request.POST.get("contact", "").strip()
        location = request.POST.get("location", "").strip()
        description = request.POST.get("description", "").strip()
        category = request.POST.get("category", "").strip()
        client_email = request.user.email

        # Basic validation
        if not all([name, contact, location, category]):
            messages.error(request, "All fields except description and photo are required.")
            return redirect("add_problem")

        # Default photo_url to empty
        photo_url = ""

        # Process file upload if a photo is attached
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

        # Build problem data
        problem_data = {
            "client_email": client_email,
            "name": name,
            "contact": contact,
            "location": location,
            "description": description if description else None,
            "photo_url": photo_url if photo_url else None,
            "category": category,
        }

        # Insert into Supabase "problems" table
        try:
            insert_response = supabase.table("problems").insert(problem_data).execute()
            if not insert_response.data:
                raise Exception("Insert returned no data - possible schema mismatch or server error")
            messages.success(request, "Your problem has been submitted successfully!")
            return redirect("home")
        except Exception as e:
            messages.error(request, f"Error submitting problem: {str(e)}")
            return redirect("add_problem")

    # For GET request, provide category options
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

    problems_response = supabase.table("problems").select("*").order("created_at", desc=False).execute()
    problems = problems_response.data if problems_response.data else []

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

    # Fetch the problem by its ID
    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    if not problem_response.data:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")

    problem = problem_response.data[0]

    # Fetch bids for the problem
    bids_response = supabase.table("bids").select("*").eq("problem_id", problem_id).execute()
    bids = bids_response.data if bids_response.data else []

    # Fetch assigned repairman (if any)
    assigned_response = supabase.table("assigned_problems").select("repairman_email").eq("problem_id", problem_id).execute()
    assigned_repairman = assigned_response.data[0]["repairman_email"] if assigned_response.data else None

    # Pass the problem, bids, and assigned repairman data to the template
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

        # Insert bid into the `bids` table
        bid_data = {
            "problem_id": problem_id,
            "repairman_email": repairman_email,
            "amount": amount,
        }
        insert_response = supabase.table("bids").insert(bid_data).execute()
        print("Bid insert response:", insert_response)

        messages.success(request, "Your bid has been submitted successfully!")
        return redirect("available_problems")

    # For GET request, render the bid form
    return render(request, "submit_bid.html", {"problem_id": problem_id})
def select_repairman_view(request, problem_id, repairman_email):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to select a repairman.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'client':
        messages.error(request, "Only clients can select repairmen.")
        return redirect("home")

    # Fetch the problem by its ID
    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    if not problem_response.data:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")

    problem = problem_response.data[0]

    # Move the problem to the `assigned_problems` table
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

    # Delete the problem from the `problems` table
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
        # Fetch problems assigned to the client
        response = supabase.table("assigned_problems").select("*").eq("client_email", user_email).execute()
    else:
        # Fetch problems assigned to the repairman
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

    # Fetch problems posted by the logged-in client
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

    # Fetch problems assigned to the logged-in repairman
    repairman_email = request.user.email
    assigned_response = supabase.table("assigned_problems").select("*").eq("repairman_email", repairman_email).execute()
    assigned_problems = assigned_response.data if assigned_response.data else []

    # Fetch additional details for each assigned problem
    for problem in assigned_problems:
        problem_id = problem["problem_id"]
        problem_details_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
        if problem_details_response.data:
            problem.update(problem_details_response.data[0])

    return render(request, "my_assigned_problems.html", {"assigned_problems": assigned_problems})