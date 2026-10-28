
"""
Voice Interface - Main Controller
Programming Design Project
"""

try:
    from speech_output import speak
except ImportError:
    from speech_output import speak

# speak() --> speaks text included inside parenthesis

def main():

    print("Voice Interface Starting...")

    speak("Welcome to your personal assistant.")

    print("Voice Interface Ready.")


if __name__ == "__main__":
    main()
