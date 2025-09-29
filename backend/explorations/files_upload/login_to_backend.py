# ==============================================================================
# LOCAL TEST CLIENT FOR A PRIVATE GOOGLE CLOUD RUN SERVICE
# ==============================================================================
#
# Description:
# This script helps you test your private Cloud Run backend from your local
# machine. It programmatically fetches a Google-signed identity token for your
# user account and uses it to make an authenticated API call.
#
# Author: Gemini
# Date: September 22, 2025
#
# ==============================================================================
#
#  --- SETUP & INSTRUCTIONS ---
#
# 1. INSTALL LIBRARIES:
#    -------------------
#    Install the necessary Python libraries by running this command in your terminal:
#    pip install google-auth requests python-dotenv
#
# 2. AUTHENTICATE YOUR LOCAL SDK:
#    -----------------------------
#    This script uses your own Google Cloud account credentials to get a token.
#    Run this command ONCE in your terminal to log in and save your credentials
#    where the script can find them.
#
#    gcloud auth application-default login
#
#    This command authenticates you as a user with the ability to "invoke" the
#    Cloud Run service. Make sure your user account has the "Cloud Run Invoker"
#    role on the project or on the specific service.
#
# 3. CREATE A .env FILE:
#    --------------------
#    To avoid hardcoding URLs or other settings, create a file named `.env` in the
#    same directory as this script. This file will hold your environment variables.
#
#    Add the following line to your .env file, replacing with your service's URL:
#    SERVICE_URL="https://probtp-poc-backend-prod-824380748826.europe-west9.run.app"
#
# ==============================================================================

import os
import subprocess

import google.auth
import google.auth.transport.requests
import google.oauth2.credentials
import requests
from dotenv import load_dotenv
from google.auth.transport.urllib3 import Request
from google.oauth2 import id_token

# Load environment variables from the .env file
load_dotenv()

def get_identity_token(service_url: str) -> str:
    """
    Fetches a Google-signed identity token for the specified service URL.
    
    This function uses the Application Default Credentials (ADC) set up by the
    `gcloud auth application-default login` command.
    
    Args:
        service_url: The URL of the Cloud Run service (this is the "audience").

    Returns:
        A Google-signed OIDC identity token as a string.
    """
    print(f"🔑 Authenticating and fetching identity token for audience: {service_url}")
    
    try:
        # First, try the standard approach
        auth_req = google.auth.transport.requests.Request()
        
        try:
            # Try to fetch identity token directly
            identity_token = id_token.fetch_id_token(auth_req, service_url)
            print("✅ Successfully fetched identity token using direct method.")
            return identity_token
        except Exception as direct_error:
            print(f"⚠️ Direct method failed: {direct_error}")
            print("🔄 Trying gcloud CLI approach...")
            
            # Use gcloud CLI to get identity token - try both methods
            try:
                # First try with audiences (for service accounts)
                result = subprocess.run([
                    'gcloud', 'auth', 'print-identity-token',
                    '--audiences', service_url
                ], capture_output=True, text=True, check=True)
                
                identity_token = result.stdout.strip()
                if identity_token:
                    print("✅ Successfully fetched identity token using gcloud CLI with audiences.")
                    return identity_token
                    
            except subprocess.CalledProcessError as e:
                print(f"⚠️ gcloud CLI method with audiences failed (expected for user accounts): {e.stderr.strip() if e.stderr else 'Unknown error'}")
                
                # Try without audiences (for user accounts)
                try:
                    result = subprocess.run([
                        'gcloud', 'auth', 'print-identity-token'
                    ], capture_output=True, text=True, check=True)
                    
                    identity_token = result.stdout.strip()
                    if identity_token:
                        print("✅ Successfully fetched identity token using gcloud CLI without audiences.")
                        return identity_token
                    else:
                        raise Exception("Empty token received from gcloud")
                        
                except subprocess.CalledProcessError as e2:
                    print(f"⚠️ gcloud CLI method without audiences also failed: {e2}")
                    print("🔄 Trying fallback approach with access token...")
                
                # Fallback: get credentials and use access token
                creds, project_id = google.auth.default()
                print(f"📝 Using project: {project_id}")
                
                # Refresh credentials if needed
                if hasattr(creds, 'expired') and creds.expired:
                    print("🔄 Refreshing expired credentials...")
                    creds.refresh(auth_req)
                
                # For user credentials, we might need to use the access token instead
                if hasattr(creds, 'token'):
                    print("⚠️ Using access token (may not work for all Cloud Run services).")
                    return creds.token
                else:
                    # Last resort: try to get identity token with refreshed creds
                    identity_token = id_token.fetch_id_token(auth_req, service_url)
                    print("✅ Successfully fetched identity token after credential refresh.")
                    return identity_token
        
    except google.auth.exceptions.DefaultCredentialsError as e:
        print(f"❌ Authentication error: {e}")
        print("\n🛠️  TROUBLESHOOTING STEPS:")
        print("1. Run: gcloud auth application-default login")
        print("2. Make sure you're authenticated: gcloud auth list")
        print("3. Set your project: gcloud config set project YOUR_PROJECT_ID")
        print("4. Check your credentials file exists:")
        print("   - macOS/Linux: ~/.config/gcloud/application_default_credentials.json")
        print("   - Windows: %APPDATA%\\gcloud\\application_default_credentials.json")
        print("\n🔍 ALTERNATIVE: Try running:")
        print("   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform")
        raise
    except Exception as e:
        print(f"❌ Unexpected error during authentication: {e}")
        print(f"Error type: {type(e).__name__}")
        raise

def make_authenticated_request(service_url: str, token: str, endpoint: str = "/"):
    """
    Makes an authenticated GET request to a specific endpoint of the Cloud Run service.

    Args:
        service_url: The base URL of the Cloud Run service.
        token: The identity token for authentication.
        endpoint: The specific API endpoint to test (e.g., "/api/health").
    """
    full_url = f"{service_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"🚀 Making authenticated request to: {full_url}")
    
    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        print("\n--- SUCCESS ---")
        print(f"Status Code: {response.status_code}")
        print("Response Body:")
        try:
            # Try to print as JSON if possible, otherwise fall back to text
            print(response.json())
        except requests.exceptions.JSONDecodeError:
            print(response.text)
            
    except requests.exceptions.HTTPError as e:
        print("\n--- ERROR ---")
        print(f"HTTP Error: {e.response.status_code} {e.response.reason}")
        print("Response Body:")
        print(e.response.text)
    except requests.exceptions.RequestException as e:
        print(f"\n--- REQUEST FAILED ---")
        print(f"An error occurred: {e}")

def main():
    """Main function to run the test client."""
    service_url = os.getenv("SERVICE_URL")
    if not service_url:
        print("❌ Error: SERVICE_URL not found in .env file.")
        print("Please create a .env file and add: SERVICE_URL=\"https://your-service-url...\"")
        return

    try:
        token = get_identity_token(service_url)
        
        # ===> DEFINE YOUR TEST HERE <===
        # Change the endpoint to whatever you want to test.
        # For a simple health check, it's often the root "/" or "/health".
        endpoint_to_test = "/" 
        
        make_authenticated_request(service_url, token, endpoint_to_test)
        
    except Exception as e:
        print(f"\nAn unexpected error occurred during the process: {e}")


if __name__ == "__main__":
    main()

# ==============================================================================
#
#  --- ADVICE ON MANAGING SECRETS (e.g., API Keys, DB Passwords) ---
#
# Storing secrets in a .env file is convenient but NOT secure. The best practice,
# even for local development, is to use Google Secret Manager.
#
# HOW IT WORKS:
# Your local, authenticated user (`gcloud auth application-default login`) is
# granted permission to READ secrets from Secret Manager. Your local script then
# fetches them directly from the cloud at runtime. This mimics the production
# behavior and keeps secrets out of your source code and local files.
#
# STEPS:
# 1. Grant Permission:
#    In the GCP Console (or via gcloud), give your user account
#    (e.g., your-email@gmail.com) the "Secret Manager Secret Accessor" role.
#
# 2. Add Code to Fetch Secrets:
#    Use the Google Cloud client library to fetch secrets in your app.
#
#    First, install it: `pip install google-cloud-secret-manager`
#
#    Then, use a function like this in your code:
#
#    from google.cloud import secretmanager
#
#    def get_secret(project_id: str, secret_id: str, version_id: str = "latest") -> str:
#        """Fetches a secret from Google Secret Manager."""
#        client = secretmanager.SecretManagerServiceClient()
#        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
#        response = client.access_secret_version(request={"name": name})
#        return response.payload.data.decode("UTF-8")
#
#    # --- Example Usage ---
#    # project_id = "your-gcp-project-id"
#    # db_password = get_secret(project_id, "db-password")
#    # api_key = get_secret(project_id, "sendgrid-api-key")
#
# This approach is secure, scalable, and makes your local environment behave
# almost identically to production.
#
# ==============================================================================
