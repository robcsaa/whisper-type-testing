#!/usr/bin/env python3
import os
import sys
import json
import queue
import threading
import signal
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller, Key
import whisper
import time
from pathlib import Path
import resampy

class VoiceToText:
    def __init__(self):
        self.recording = False
        self.keyboard_controller = Controller()
        self.current_keys = set()
        self.running = True
        self.audio_data = []
        self.target_samplerate = 16000  # Whisper also expects 16kHz
        self.current_samplerate = None  # Will be set when recording starts
        self.resample_buffer = []  # Buffer for resampling
        self.last_recognized_text = ""  # Track last recognized text
        self.model_size = "tiny.en"  # Smaller model, may work better for a single speaker
        self.debug_level = 1  # 0=minimal, 1=normal, 2=verbose
        self.save_recordings = False  # Set to True to save audio recordings for training
        self.recordings_dir = Path("voice_samples")  # Directory to save recordings
        if self.save_recordings:
            self.recordings_dir.mkdir(exist_ok=True)
        self.setup_model()
        
    def debug_print(self, message, level=1):
        """Print debug messages based on debug level"""
        if level <= self.debug_level:
            print(message)
        
    def setup_model(self):
        """Setup the Whisper model"""
        self.debug_print(f"Loading Whisper model: {self.model_size}", 0)
        try:
            self.model = whisper.load_model(self.model_size)
            self.debug_print("Whisper model loaded successfully", 0)
        except Exception as e:
            self.debug_print(f"Error loading Whisper model: {e}", 0)
            sys.exit(1)

    def audio_callback(self, indata, frames, time, status):
        """Callback for audio recording"""
        if status:
            self.debug_print(f"Audio status: {status}", 2)
        
        # Get raw audio data
        audio_data = indata.flatten()
        
        # Show audio statistics at debug level 2
        if self.debug_level >= 2:
            self.debug_print(f"Raw input shape: {indata.shape}, mean: {np.mean(audio_data):.6f}, min: {np.min(audio_data):.6f}, max: {np.max(audio_data):.6f}", 2)
        
        # Skip processing if the audio is too quiet
        if np.max(np.abs(audio_data)) < 0.0005:  # Lower threshold to capture more audio
            if self.debug_level >= 2:
                self.debug_print("Audio too quiet, skipping", 2)
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
                
                # Store the audio data for final processing (as float32 for Whisper)
                self.audio_data.append(resampled_data)
                
                # Clear buffer
                self.resample_buffer = []
            except Exception as e:
                self.debug_print(f"Error processing audio chunk: {e}", 0)
                self.resample_buffer = []

    def record_audio(self):
        """Record audio from microphone"""
        self.debug_print("\n=== Starting Audio Recording ===", 0)
        try:
            # Find the microphone device
            devices = sd.query_devices()
            mic_device = None
            
            # First try to find the PipeWire device
            for i, device in enumerate(devices):
                if 'pipewire' in str(device['name']).lower():
                    mic_device = i
                    self.debug_print(f"Found PipeWire device: {device['name']}", 1)
                    break
            
            # If no PipeWire device, try ALC245
            if mic_device is None:
                for i, device in enumerate(devices):
                    if 'ALC245' in str(device['name']):
                        mic_device = i
                        self.debug_print(f"Found ALC245 device: {device['name']}", 1)
                        break
            
            # If still not found, use default input device
            if mic_device is None:
                for i, device in enumerate(devices):
                    if device['max_input_channels'] > 0:
                        mic_device = i
                        self.debug_print(f"Using default input device: {device['name']}", 1)
                        break
            
            if mic_device is None:
                self.debug_print("Error: No input device found", 0)
                return
            
            device_info = sd.query_devices(mic_device)
            self.debug_print(f"\nUsing input device: {device_info['name']} (ID: {mic_device})", 1)
            
            # Get device's native sample rate
            self.current_samplerate = int(device_info['default_samplerate'])
            self.debug_print(f"Device sample rate: {self.current_samplerate} Hz", 1)
            
            # Configure audio stream with explicit device
            with sd.InputStream(device=mic_device,
                              samplerate=self.current_samplerate,
                              channels=1,
                              dtype='float32',
                              callback=self.audio_callback,
                              blocksize=1024) as stream:  # Smaller blocksize for better responsiveness
                self.debug_print("\nAudio stream opened successfully", 1)
                self.debug_print("Waiting for audio data...", 1)
                while self.recording and self.running:
                    time.sleep(0.1)
        except Exception as e:
            self.debug_print(f"Error in audio recording: {e}", 0)
            import traceback
            traceback.print_exc()

    def toggle_recording(self):
        """Toggle recording state"""
        self.recording = not self.recording
        if self.recording:
            self.debug_print("Recording started...", 0)
            self.audio_data = []  # Clear previous audio data
            threading.Thread(target=self.record_audio).start()
        else:
            self.debug_print("Recording stopped, processing...", 0)
            
            # Process any remaining audio in the buffer
            if self.resample_buffer:
                try:
                    audio_data = np.concatenate(self.resample_buffer)
                    if self.current_samplerate != self.target_samplerate:
                        audio_data = resampy.resample(audio_data, self.current_samplerate, self.target_samplerate)
                    self.audio_data.append(audio_data)
                    self.resample_buffer = []
                except Exception as e:
                    self.debug_print(f"Error processing final buffer: {e}", 0)
            
            # Get final result
            try:
                if self.audio_data:
                    # Combine all audio for best recognition
                    combined_audio = np.concatenate(self.audio_data)
                    
                    # Save audio if enabled
                    if self.save_recordings:
                        self.save_audio(combined_audio)
                    
                    # Normalize audio to correct range for Whisper
                    # Whisper expects audio in the range [-1, 1]
                    self.debug_print(f"Processing audio with shape: {combined_audio.shape}", 2)
                    
                    # Process with Whisper
                    self.debug_print("Transcribing with Whisper...", 1)
                    result = self.model.transcribe(combined_audio, language="en")
                    
                    if result["text"].strip():
                        text = result["text"].strip()
                        self.debug_print(f"Final recognized text: {text}", 0)
                        self.insert_text(text)
                    else:
                        self.debug_print("No text recognized", 0)
                else:
                    self.debug_print("No audio data collected", 0)
            except Exception as e:
                self.debug_print(f"Error transcribing with Whisper: {e}", 0)
                import traceback
                traceback.print_exc()
            
            self.debug_print("Done!", 0)
            
    def save_audio(self, audio_data):
        """Save audio data to a file for training purposes"""
        try:
            import soundfile as sf
            timestamp = int(time.time())
            filename = self.recordings_dir / f"recording_{timestamp}.wav"
            sf.write(filename, audio_data, self.target_samplerate)
            self.debug_print(f"Saved audio to {filename}", 1)
        except Exception as e:
            self.debug_print(f"Error saving audio: {e}", 0)

    def insert_text(self, text):
        """Insert text at current cursor position"""
        if text.strip():
            self.debug_print(f"Inserting text: {text}", 1)
            try:
                self.keyboard_controller.type(text)
                self.debug_print("Text inserted successfully", 1)
            except Exception as e:
                self.debug_print(f"Error inserting text: {e}", 0)
        else:
            self.debug_print("No text to insert", 1)

    def on_press(self, key):
        """Handle key press events"""
        try:
            self.current_keys.add(key)
            
            # Check for Ctrl+Alt+V hotkey
            if (Key.ctrl_l in self.current_keys or Key.ctrl_r in self.current_keys) and \
               (Key.alt_l in self.current_keys or Key.alt_r in self.current_keys) and \
               (hasattr(key, 'char') and key.char == 'v'):
                self.debug_print("Hotkey detected: Ctrl+Alt+V", 1)
                # Remove the keys to prevent double triggering
                self.current_keys.clear()
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
        self.debug_print("\nCleaning up...", 1)
        self.running = False
        self.recording = False
        time.sleep(0.1)  # Give threads time to finish
        self.debug_print("Cleanup complete", 1)

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
    
    print("Voice to Text ready!")
    print("Press Ctrl+Alt+V to start/stop recording")
    
    # Setup signal handler for clean exit
    def signal_handler(sig, frame):
        print("\nExiting...")
        vtt.cleanup()
        listener.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Keep the program running
    try:
        while vtt.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        vtt.cleanup()
        listener.stop()

if __name__ == "__main__":
    main() 