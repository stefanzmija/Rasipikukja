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
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')  # 'client' or 'repairman'
        # If repairman, capture repair_category; else, it remains None.
        repair_category = request.POST.get('repair_category') if user_type == 'repairman' else None

        # Sign up the user in Supabase Auth.
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        print("Auth signup response:", auth_response)

        if auth_response.user:
            # Build profile data for insertion into the 'profiles' table.
            profile_data = {
                "email": email,
                "name": name,
                "user_type": user_type,
            }
            if user_type == 'repairman':
                profile_data["repair_category"] = repair_category
                profile_data["rating"] = 0  # Initialize rating.
            insert_response = supabase.table("profiles").insert(profile_data).execute()
            print("Profile insert response:", insert_response)

            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
        else:
            error_msg = getattr(auth_response, 'error', 'Unknown error')
            messages.error(request, f"Sign-up failed: {error_msg}")
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
    if request.method == "POST":
        rating = request.POST.get("rating")
        review = request.POST.get("review")

        if not rating or not review:
            messages.error(request, "Please provide both rating and review.")
            return redirect("rate_repairman", repairman_email=repairman_email)

        supabase.table("ratings").insert({
            "repairman_email": repairman_email,
            "user_email": request.user.email,
            "rating": rating,
            "review": review,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        messages.success(request, "Your rating has been submitted.")
        return redirect("repairmen_all")

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
    # Ensure user is logged in
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to add a problem.")
        return redirect("login")

    # Only allow clients to add problems
    if request.session.get("user_type", "client") != "client":
        messages.error(request, "Only clients can add problems.")
        return redirect("home")

    if request.method == "POST":
        # Retrieve form data
        name = request.POST.get("name", "").strip()
        contact = request.POST.get("contact", "").strip()
        location = request.POST.get("location", "").strip()
        description = request.POST.get("description", "").strip()
        client_email = request.user.email

        # Default photo_url to empty
        photo_url = ""

        # Process file upload if a photo is attached
        if "photo" in request.FILES:
            photo_file = request.FILES["photo"]
            print("Received photo file:", photo_file.name)
            # Validate that the file is PNG
            if not photo_file.name.lower().endswith(".png"):
                messages.error(request, "Only PNG files are allowed for the photo.")
                return redirect("add_problem")

            # Generate a unique filename
            file_name = f"problem_{int(time.time())}_{photo_file.name}"
            print("Generated file name:", file_name)

            # Write the uploaded file to a temporary file
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    # Use shutil.copyfileobj for efficient copying
                    shutil.copyfileobj(photo_file.file, tmp)
                    tmp_path = tmp.name
                print("Temporary file created at:", tmp_path)
            except Exception as e:
                print("Error writing temporary file:", e)
                messages.error(request, f"Error saving file locally: {e}")
                return redirect("add_problem")

            # Upload the temporary file to Supabase Storage (bucket: "problem-photos")
            try:
                upload_response = supabase.storage.from_("problem-photos").upload(file_name, tmp_path)
                print("Upload response:", upload_response)
            except Exception as e:
                print("Error during file upload:", e)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                messages.error(request, f"Error uploading file: {e}")
                return redirect("add_problem")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    print("Temporary file removed.")

            # Check upload response status if available
            if hasattr(upload_response, "status_code"):
                if upload_response.status_code not in [200, 201]:
                    messages.error(request, f"Photo upload failed with status {upload_response.status_code}")
                    return redirect("add_problem")

            # Retrieve the public URL of the uploaded file
            try:
                public_url_response = supabase.storage.from_("problem-photos").get_public_url(file_name)
                print("Public URL response:", public_url_response)
                # Assume response is a dict with a "data" key containing {"publicUrl": "http://..."}
                photo_url = public_url_response.get("data", {}).get("publicUrl", "")
                print("Extracted photo_url:", photo_url)
                if not photo_url:
                    messages.error(request, "Failed to retrieve the public URL for the photo.")
                    return redirect("add_problem")
            except Exception as e:
                print("Error retrieving public URL:", e)
                messages.error(request, f"Error retrieving public URL: {e}")
                return redirect("add_problem")

        # Build problem data
        problem_data = {
            "client_email": client_email,
            "name": name,
            "contact": contact,
            "location": location,
            "description": description,
            "photo_url": photo_url,
        }
        print("Problem data to insert:", problem_data)

        # Insert the problem record into the "problems" table in Supabase
        try:
            insert_response = supabase.table("problems").insert(problem_data).execute()
            print("Problem insert response:", insert_response)
        except Exception as e:
            print("Error inserting problem:", e)
            messages.error(request, f"Error inserting problem: {e}")
            return redirect("add_problem")

        messages.success(request, "Your problem has been submitted successfully!")
        return redirect("home")

    # For GET request, simply render the form template
    return render(request, "add_problem.html")

def available_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view available problems.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can view available problems.")
        return redirect("home")
    problems_response = supabase.table("problems").select("*").order("created_at", desc=False).execute()
    problems = problems_response.data if problems_response.data else []
    return render(request, "available_problems.html", {"problems": problems})

def problem_detail_view(request, problem_id):
    """
    Shows detailed info about a single problem, accessible only to repairmen.
    """
    # Ensure user is logged in
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view problem details.")
        return redirect("login")

    # Ensure user is a repairman
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can view problem details.")
        return redirect("home")

    # Fetch the problem by its ID
    response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    if not response.data:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")

    problem = response.data[0]

    # Pass the problem data to the template
    return render(request, "problem_detail.html", {"problem": problem})

def submit_bid_view(request, problem_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to submit a bid.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'repairman':
        messages.error(request, "Only repairmen can submit bids.")
        return redirect("home")

    if request.method == "POST":
        bid_amount = request.POST.get("bid_amount")
        comment = request.POST.get("comment")
        repairman_email = request.user.email

        bid_data = {
            "problem_id": problem_id,
            "repairman_email": repairman_email,
            "bid_amount": bid_amount,
            "comment": comment,
            "status": "pending"
        }
        try:
            insert_response = supabase.table("bids").insert(bid_data).execute()
            print("Bid insert response:", insert_response)
            messages.success(request, "Bid submitted successfully!")
            return redirect("available_problems")
        except Exception as e:
            print("Error inserting bid:", e)
            messages.error(request, f"Error submitting bid: {e}")
            return redirect("submit_bid", problem_id=problem_id)

    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    problem = problem_response.data[0] if problem_response.data else None
    if not problem:
        messages.error(request, "Problem not found.")
        return redirect("available_problems")
    return render(request, "submit_bid.html", {"problem": problem})

def select_repairman_view(request, problem_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to select a repairman.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'client':
        messages.error(request, "Only clients can select a repairman.")
        return redirect("home")

    if request.method == "POST":
        repairman_email = request.POST.get("repairman_email")
        if not repairman_email:
            messages.error(request, "Please select a repairman.")
            return redirect("select_repairman", problem_id=problem_id)

        update_data = {"assigned_repairman": repairman_email, "status": "assigned"}
        try:
            update_response = supabase.table("problems").update(update_data).eq("id", problem_id).execute()
            if not update_response.data:
                raise Exception("Update returned no data")
            print("Repairman selection update response:", update_response)
            messages.success(request, "Repairman selected successfully!")
            return redirect("my_problems")
        except Exception as e:
            print("Error updating problem:", e)
            messages.error(request, f"Error selecting repairman: {e}")
            return redirect("select_repairman", problem_id=problem_id)

    bids_response = supabase.table("bids").select("*").eq("problem_id", problem_id).eq("status", "pending").execute()
    bids = bids_response.data if bids_response.data else []
    problem_response = supabase.table("problems").select("*").eq("id", problem_id).execute()
    problem = problem_response.data[0] if problem_response.data else None
    if not problem:
        messages.error(request, "Problem not found.")
        return redirect("home")
    return render(request, "select_repairman.html", {"problem": problem, "bids": bids})

def pending_problems_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view pending problems.")
        return redirect("login")
    if request.session.get('user_type', 'client') != 'client':
        messages.error(request, "Only clients can view pending problems.")
        return redirect("home")

    email = request.user.email
    problems_response = supabase.table("problems").select("*").eq("client_email", email).is_("assigned_repairman", None).execute()
    pending_problems = problems_response.data if problems_response.data else []
    return render(request, "pending_problems.html", {"pending_problems": pending_problems})