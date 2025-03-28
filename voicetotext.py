#!/usr/bin/env python3
import os
import sys
import json
import wave
import queue
import threading
import signal
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller, Key
from vosk import Model, KaldiRecognizer
import time
from pathlib import Path
import resampy

class VoiceToText:
    def __init__(self):
        self.recording = False
        self.keyboard_controller = Controller()
        self.model_path = Path.home() / '.vosk' / 'model' / 'vosk-model-en-us-0.22'
        self.current_keys = set()
        self.running = True
        self.audio_data = []
        self.target_samplerate = 16000  # Vosk expects 16kHz
        self.current_samplerate = None  # Will be set when recording starts
        self.resample_buffer = []  # Buffer for resampling
        self.last_recognized_text = ""  # Track last recognized text
        self.setup_model()
        
    def setup_model(self):
        """Download and setup the Vosk model if not present"""
        if not self.model_path.exists():
            print("Downloading Vosk model...")
            # TODO: Implement model download
            print("Please download the model manually from https://alphacephei.com/vosk/models")
            print("and extract it to ~/.vosk/model/vosk-model-en-us-0.22")
            sys.exit(1)
        
        self.model = Model(str(self.model_path))
        self.recognizer = KaldiRecognizer(self.model, self.target_samplerate)

    def audio_callback(self, indata, frames, time, status):
        """Callback for audio recording"""
        if status:
            print(f"Audio status: {status}")
        
        # Get raw audio data
        audio_data = indata.flatten()
        
        # Skip processing if the audio is too quiet
        if np.max(np.abs(audio_data)) < 0.0001:
            return
        
        # Add to resample buffer
        self.resample_buffer.append(audio_data)
        
        # Process when we have enough data
        if len(self.resample_buffer) >= 4:
            try:
                # Concatenate buffer
                buffer_data = np.concatenate(self.resample_buffer)
                
                # Resample to 16kHz
                resampled_data = resampy.resample(buffer_data, self.current_samplerate, self.target_samplerate)
                
                # Convert to 16-bit PCM
                audio_int16 = (resampled_data * 32767).astype(np.int16)
                
                # Store the audio data for final processing
                audio_bytes = audio_int16.tobytes()
                self.audio_data.append(audio_bytes)
                
                # Process audio if we're recording
                if self.recording:
                    self.recognizer.AcceptWaveform(audio_bytes)
                
                # Clear buffer
                self.resample_buffer = []
            except Exception as e:
                print(f"Error processing audio chunk: {e}")
                self.resample_buffer = []

    def record_audio(self):
        """Record audio from microphone"""
        print("\n=== Starting Audio Recording ===")
        try:
            # Find the microphone device
            devices = sd.query_devices()
            mic_device = None
            
            # First try to find the PipeWire device
            for i, device in enumerate(devices):
                if 'pipewire' in str(device['name']).lower():
                    mic_device = i
                    print(f"Found PipeWire device: {device['name']}")
                    break
            
            # If no PipeWire device, try ALC245
            if mic_device is None:
                for i, device in enumerate(devices):
                    if 'ALC245' in str(device['name']):
                        mic_device = i
                        print(f"Found ALC245 device: {device['name']}")
                        break
            
            # If still not found, use default input device
            if mic_device is None:
                for i, device in enumerate(devices):
                    if device['max_input_channels'] > 0:
                        mic_device = i
                        print(f"Using default input device: {device['name']}")
                        break
            
            if mic_device is None:
                print("Error: No input device found")
                return
            
            device_info = sd.query_devices(mic_device)
            print(f"\nUsing input device: {device_info['name']} (ID: {mic_device})")
            
            # Get device's native sample rate
            self.current_samplerate = int(device_info['default_samplerate'])
            print(f"Device sample rate: {self.current_samplerate} Hz")
            
            # Configure audio stream with explicit device
            with sd.InputStream(device=mic_device,
                              samplerate=self.current_samplerate,
                              channels=1,
                              dtype='float32',
                              callback=self.audio_callback,
                              blocksize=4096) as stream:
                print("\nAudio stream opened successfully")
                print("Waiting for audio data...")
                while self.recording and self.running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"Error in audio recording: {e}")
            import traceback
            traceback.print_exc()

    def toggle_recording(self):
        """Toggle recording state"""
        self.recording = not self.recording
        if self.recording:
            print("Recording started...")
            self.audio_data = []  # Clear previous audio data
            # Reset recognizer for new recording
            self.recognizer = KaldiRecognizer(self.model, self.target_samplerate)
            threading.Thread(target=self.record_audio).start()
        else:
            print("Recording stopped, processing...")
            
            # Process any remaining audio in the buffer
            if self.resample_buffer:
                try:
                    audio_data = np.concatenate(self.resample_buffer)
                    if self.current_samplerate != self.target_samplerate:
                        audio_data = resampy.resample(audio_data, self.current_samplerate, self.target_samplerate)
                    audio_data = (audio_data * 32767).astype(np.int16)
                    self.audio_data.append(audio_data.tobytes())
                    self.resample_buffer = []
                except Exception as e:
                    print(f"Error processing final buffer: {e}")
            
            # Get final result
            try:
                # Create a new recognizer for final processing
                final_recognizer = KaldiRecognizer(self.model, self.target_samplerate)
                
                if self.audio_data:
                    # Combine all audio for best recognition
                    combined_audio = b"".join(self.audio_data)
                    
                    # Process the combined audio
                    final_recognizer.AcceptWaveform(combined_audio)
                    final_result = json.loads(final_recognizer.FinalResult())
                    
                    if final_result.get("text", "").strip():
                        text = final_result["text"]
                        print(f"Final recognized text: {text}")
                        self.insert_text(text)
                    else:
                        print("No text recognized")
                else:
                    print("No audio data collected")
            except Exception as e:
                print(f"Error getting final result: {e}")
            
            print("Done!")

    def insert_text(self, text):
        """Insert text at current cursor position"""
        if text.strip():
            print(f"Inserting text: {text}")
            try:
                self.keyboard_controller.type(text)
                print("Text inserted successfully")
            except Exception as e:
                print(f"Error inserting text: {e}")
        else:
            print("No text to insert")

    def on_press(self, key):
        """Handle key press events"""
        try:
            self.current_keys.add(key)
            
            # Check for Ctrl+Alt+V hotkey
            if (Key.ctrl_l in self.current_keys or Key.ctrl_r in self.current_keys) and \
               (Key.alt_l in self.current_keys or Key.alt_r in self.current_keys) and \
               (hasattr(key, 'char') and key.char == 'v'):
                print("Hotkey detected: Ctrl+Alt+V")
                self.toggle_recording()
        except AttributeError:
            pass

    def on_release(self, key):
        """Handle key release events"""
        try:
            self.current_keys.discard(key)
        except KeyError:
            pass

    def cleanup(self):
        """Cleanup resources"""
        print("\nCleaning up...")
        self.running = False
        self.recording = False
        time.sleep(0.1)  # Give threads time to finish
        print("Cleanup complete")

def main():
    # Set the audio backend configuration
    try:
        sd.default.device = None  # Use system default
        sd.default.samplerate = 44100  # Common sample rate
        sd.default.channels = 1  # Mono for voice
        sd.default.dtype = 'float32'  # Higher precision
        print("Audio backend configuration successful")
    except Exception as e:
        print(f"Warning: Could not configure audio backend: {e}")
    
    vtt = VoiceToText()
    
    # Setup keyboard listener
    listener = keyboard.Listener(
        on_press=vtt.on_press,
        on_release=vtt.on_release)
    listener.start()
    
    # Register signal handler
    def signal_handler(signum, frame):
        print("\nExiting...")
        vtt.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Voice to Text is running. Press Ctrl+Alt+V to start/stop recording.")
    print("Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        vtt.cleanup()

if __name__ == "__main__":
    main() 