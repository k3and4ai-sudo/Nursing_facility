import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: {CREDENTIALS_FILE} not found.")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    print("\n" + "="*70)
    print("Google Fit 連携の認可を開始します。")
    print("以下のブラウザ認証を完了してください。")
    print("="*70 + "\n")
    
    # Run local server on an available port with automatic browser popup
    creds = flow.run_local_server(port=8090, prompt="consent", access_type="offline")
    
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())
        
    print("\n" + "="*70)
    print("✅ 認証が正常に完了しました！ token.json を保存しました。")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
