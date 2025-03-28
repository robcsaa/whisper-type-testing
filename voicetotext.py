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
        self.audio_queue = queue.Queue()
        self.keyboard_controller = Controller()
        self.model_path = Path.home() / '.vosk' / 'model' / 'vosk-model-en-us-0.22'
        self.current_keys = set()
        self.running = True
        self.audio_data = []
        self.target_samplerate = 16000  # Vosk expects 16kHz
        self.current_samplerate = None  # Will be set when recording starts
        self.resample_buffer = []  # Buffer for resampling
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
            print(f"Audio callback status: {status}")
        
        # Check if we're getting any audio data
        if not np.any(indata):
            print("Warning: No audio data received")
            return
            
        # Convert to float32 for processing
        audio_data = indata.astype(np.float32)
        print(f"\nRaw input - shape: {audio_data.shape}, dtype: {audio_data.dtype}")
        print(f"Raw input stats - mean: {np.mean(audio_data):.2f}, min: {np.min(audio_data):.2f}, max: {np.max(audio_data):.2f}")
        
        # Remove DC offset
        audio_data = audio_data - np.mean(audio_data)
        print(f"After DC offset removal - mean: {np.mean(audio_data):.2f}, min: {np.min(audio_data):.2f}, max: {np.max(audio_data):.2f}")
        
        # Add to resample buffer (flatten the array)
        self.resample_buffer.append(audio_data.flatten())
        
        # Resample when we have enough samples
        if len(self.resample_buffer) >= 4:  # Accumulate 4 chunks before resampling
            # Concatenate the buffer
            audio_data = np.concatenate(self.resample_buffer)
            print(f"Buffer size before resampling: {len(audio_data)}")
            
            # Resample to 16kHz if needed
            if self.current_samplerate != self.target_samplerate:
                print(f"Resampling from {self.current_samplerate}Hz to {self.target_samplerate}Hz")
                audio_data = resampy.resample(audio_data, self.current_samplerate, self.target_samplerate)
                print(f"After resampling - shape: {audio_data.shape}, mean: {np.mean(audio_data):.2f}")
            
            # Convert to int16 for Vosk
            audio_data = (audio_data * 32767).astype(np.int16)
            print(f"Final audio - shape: {audio_data.shape}, dtype: {audio_data.dtype}")
            print(f"Final audio stats - mean: {np.mean(audio_data):.2f}, min: {np.min(audio_data)}, max: {np.max(audio_data)}")
                
            # Convert to bytes and store
            audio_bytes = audio_data.tobytes()
            print(f"Audio bytes length: {len(audio_bytes)}")
            self.audio_queue.put(audio_bytes)
            self.audio_data.append(audio_bytes)
            
            # Clear the buffer
            self.resample_buffer = []
            
            # Print audio levels for debugging
            audio_level = np.abs(audio_data).mean()
            if audio_level > 100:  # Lower threshold for better sensitivity
                print(f"Audio level: {audio_level:.2f}")

    def record_audio(self):
        """Record audio from microphone"""
        print("\n=== Starting Audio Recording ===")
        try:
            # List available devices
            print("\nAvailable audio devices:")
            print(sd.query_devices())
            
            # Find the microphone device
            devices = sd.query_devices()
            mic_device = None
            
            # First try to find the PipeWire device
            for i, device in enumerate(devices):
                if 'pipewire' in device['name'].lower():
                    mic_device = i
                    print(f"Found PipeWire device: {device['name']}")
                    break
            
            # If no PipeWire device, try ALC245
            if mic_device is None:
                for i, device in enumerate(devices):
                    if 'ALC245' in device['name']:
                        mic_device = i
                        print(f"Found ALC245 device: {device['name']}")
                        break
            
            if mic_device is None:
                print("Warning: Could not find preferred microphone")
                return
            
            device_info = sd.query_devices(mic_device)
            print(f"\nUsing input device: {device_info['name']} (ID: {mic_device})")
            print(f"Device info: {device_info}")
            
            # Get device's native sample rate
            self.current_samplerate = int(device_info['default_samplerate'])
            print(f"Device native sample rate: {self.current_samplerate}")
            print(f"Target sample rate: {self.target_samplerate}")
            
            # Configure audio stream with explicit device
            with sd.InputStream(device=mic_device,
                              samplerate=self.current_samplerate,
                              channels=1,
                              dtype='float32',  # Use float32 for better processing
                              callback=self.audio_callback,
                              blocksize=2048,
                              latency='high') as stream:
                print("\nAudio stream opened successfully")
                print(f"Stream info: {stream}")
                print("Waiting for audio data...")
                while self.recording and self.running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"Error in audio recording: {e}")
            import traceback
            traceback.print_exc()

    def process_audio(self):
        """Process recorded audio and convert to text"""
        print("\n=== Starting Audio Processing ===")
        text = ""
        
        # Process any remaining audio in the buffer
        if self.resample_buffer:
            audio_data = np.concatenate(self.resample_buffer)
            if self.current_samplerate != self.target_samplerate:
                audio_data = resampy.resample(audio_data, self.current_samplerate, self.target_samplerate)
            audio_data = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_data.tobytes()
            self.audio_queue.put(audio_bytes)
            self.audio_data.append(audio_bytes)
            self.resample_buffer = []
        
        if not self.audio_data:
            print("Warning: No audio data to process")
            return text
            
        total_bytes = sum(len(chunk) for chunk in self.audio_data)
        print(f"Processing {len(self.audio_data)} audio chunks (total {total_bytes} bytes)...")
        
        # Process all collected audio data
        while not self.audio_queue.empty() and self.running:
            data = self.audio_queue.get()
            # Convert bytes back to numpy array to check audio level
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_level = np.abs(audio_data).mean()
            
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                print(f"Recognition result: {result}")
                if result.get("text", "").strip():
                    text = result["text"]
                    print(f"Recognized text: {text}")
            elif audio_level > 500:  # Only show "No result" if we detect speech
                print(f"No result from this chunk (audio level: {audio_level:.2f})")
        
        # Get final result
        final_result = json.loads(self.recognizer.FinalResult())
        print(f"\nFinal result: {final_result}")
        if final_result.get("text", "").strip():
            text = final_result["text"]
            print(f"Final recognized text: {text}")
        
        print("=== Audio Processing Complete ===\n")
        # Clear audio data for next recording
        self.audio_data = []
        return text

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

    def toggle_recording(self):
        """Toggle recording state"""
        self.recording = not self.recording
        if self.recording:
            print("Recording started...")
            self.audio_data = []  # Clear previous audio data
            threading.Thread(target=self.record_audio).start()
        else:
            print("Recording stopped, processing...")
            text = self.process_audio()
            if text:
                self.insert_text(text)
            print("Done!")

    def on_press(self, key):
        """Handle key press events"""
        try:
            if hasattr(key, 'char') and key.char == 'v':
                if Key.ctrl_l in self.current_keys and Key.alt_l in self.current_keys:
                    print("Hotkey detected: Ctrl+Alt+V")
                    self.toggle_recording()
        except AttributeError:
            pass

    def on_release(self, key):
        """Handle key release events"""
        pass

    def cleanup(self):
        """Cleanup resources"""
        print("\nCleaning up...")
        self.running = False
        self.recording = False
        time.sleep(0.1)  # Give threads time to finish

def main():
    # Set the audio backend configuration
    try:
        sd.default.device = None  # Reset to default device
        sd.default.samplerate = 44100  # Match common device sample rate
        sd.default.channels = 1  # Mono input
        sd.default.dtype = 'int16'  # Use 16-bit PCM
        print("Audio backend configuration successful")
    except Exception as e:
        print(f"Warning: Could not configure audio backend: {e}")
    
    vtt = VoiceToText()
    
    def on_press(key):
        try:
            vtt.current_keys.add(key)
            vtt.on_press(key)
        except AttributeError:
            pass

    def on_release(key):
        try:
            vtt.current_keys.discard(key)
            vtt.on_release(key)
        except AttributeError:
            pass

    def signal_handler(signum, frame):
        print("\nExiting...")
        vtt.cleanup()
        sys.exit(0)

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Voice to Text is running. Press Ctrl+Alt+V to start/stop recording.")
    print("Press Ctrl+C to exit.")
    
    # Start the listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    main() 