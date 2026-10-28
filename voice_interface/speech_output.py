"""
speech_output.py

Purpose for this py is to convert text into audible speech using pyttsx3

10/28/2026
    Goal: speak("How can I assist you")
    
"""

import pyttsx3 #Version 2.99


def speak(message):
    
    #verifying valid input
    if not isinstance(message,str):
        print("Error: Input must be a string")
        return False
    
    if not message.strip():
        print("Error: Cannot speak an empty message.")
        return False
    
    try:
        engine = pyttsx3.init()
        
        engine.setProperty("rate",175) #sets rate of speech
        engine.setProperty("volume",1.0) #sets speech to 100% volume *** of the engine, not of the actual speaker
        
        voices = engine.getProperty('voices')
        for voice in voices:
            engine.setProperty('voice', voice.id)
        
        engine.say(message) 
        engine.runAndWait() #generates and plays speech
        
        
        return True
    
    except (RuntimeError, OSError) as error:
        print('Speech Output Error:', error)
        return False
    



# Standalone testing 
'''
if __name__ == "__main__":

    print("Initializing voice interface...")

    speak("Howdy, The voice interface is initialized.")

    speak("Pwwincess Jeong How can I assist you?")

    print("Speech output test completed.")
    '''