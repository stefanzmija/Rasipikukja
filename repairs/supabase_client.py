# supabase_client.py
from supabase import create_client, Client
from django.conf import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,        # Set in settings.py
    settings.SUPABASE_ANON_KEY     # Set in settings.py
)
