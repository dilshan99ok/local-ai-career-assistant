"""Start the local Sign in with ChatGPT flow."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.chatgpt_auth import ChatGPTAuth, ChatGPTAuthError


if __name__ == "__main__":
    try:
        credentials = ChatGPTAuth().sign_in()
    except ChatGPTAuthError as error:
        print(f"Sign-in failed: {error}")
        raise SystemExit(1)

    email = credentials.get("email") or "the selected ChatGPT account"
    print(f"ChatGPT sign-in completed for {email}.")
    print("The career assistant can now use your ChatGPT plan for eligible requests.")
