#!/usr/bin/env python3
import os
import sys
import time
import json
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np
import whisper
from pathlib import Path

class VoiceSampleCollector:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.target_samplerate = 16000
        self.current_samplerate = None
        self.resample_buffer = []
        self.model_size = "tiny.en"
        self.sample_dir = Path("voice_samples")
        self.sample_dir.mkdir(exist_ok=True)
        self.transcription_file = self.sample_dir / "transcriptions.json"
        self.transcriptions = self.load_transcriptions()
        self.setup_model()
        
    def load_transcriptions(self):
        """Load existing transcriptions if they exist"""
        if self.transcription_file.exists():
            try:
                with open(self.transcription_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading transcriptions: {e}")
                return {}
        return {}
        
    def save_transcriptions(self):
        """Save transcriptions to json file"""
        try:
            with open(self.transcription_file, 'w') as f:
                json.dump(self.transcriptions, f, indent=2)
            print(f"Saved transcriptions to {self.transcription_file}")
        except Exception as e:
            print(f"Error saving transcriptions: {e}")
    
    def setup_model(self):
        """Setup the Whisper model"""
        try:
            print(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            print("Whisper model loaded successfully")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            sys.exit(1)

    def audio_callback(self, indata, frames, time, status):
        """Callback for audio recording"""
        if status:
            print(f"Audio status: {status}")
        
        # Get raw audio data
        audio_data = indata.flatten()
        
        # Skip processing if the audio is too quiet
        if np.max(np.abs(audio_data)) < 0.0005:
            return
        
        # Add to resample buffer
        self.resample_buffer.append(audio_data)
        
        # Process when we have enough data
        if len(self.resample_buffer) >= 4:
            try:
                # Concatenate buffer
                buffer_data = np.concatenate(self.resample_buffer)
                
                # Resample to 16kHz if needed
                if self.current_samplerate != self.target_samplerate:
                    try:
                        import resampy
                        buffer_data = resampy.resample(buffer_data, self.current_samplerate, self.target_samplerate)
                    except ImportError:
                        print("Warning: resampy not available. Using linear interpolation.")
                        # Simple resample using numpy
                        orig_len = len(buffer_data)
                        new_len = int(orig_len * self.target_samplerate / self.current_samplerate)
                        buffer_data = np.interp(
                            np.linspace(0, orig_len, new_len),
                            np.arange(orig_len),
                            buffer_data
                        )
                
                # Store the audio data for final processing
                self.audio_data.append(buffer_data)
                
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
            default_input = sd.query_devices(kind='input')
            mic_device = default_input['index']
            
            print(f"\nUsing input device: {default_input['name']} (ID: {mic_device})")
            
            # Get device's native sample rate
            self.current_samplerate = int(default_input['default_samplerate'])
            print(f"Device sample rate: {self.current_samplerate} Hz")
            
            # Configure audio stream with explicit device
            with sd.InputStream(device=mic_device,
                              samplerate=self.current_samplerate,
                              channels=1,
                              dtype='float32',
                              callback=self.audio_callback,
                              blocksize=1024) as stream:
                print("\nAudio stream opened successfully")
                print("Speak clearly into the microphone...")
                print("Recording...")
                
                # Show a timer
                start_time = time.time()
                while self.recording:
                    elapsed = time.time() - start_time
                    sys.stdout.write(f"\rRecording: {elapsed:.1f} seconds")
                    sys.stdout.flush()
                    time.sleep(0.1)
                
                print("\nRecording stopped.")
        except Exception as e:
            print(f"Error in audio recording: {e}")
            import traceback
            traceback.print_exc()

    def start_recording(self):
        """Start recording"""
        self.recording = True
        self.audio_data = []
        self.record_thread = threading.Thread(target=self.record_audio)
        self.record_thread.start()
    
    def stop_recording(self):
        """Stop recording and process audio"""
        self.recording = False
        self.record_thread.join()
        
        # Process any remaining audio in the buffer
        if self.resample_buffer:
            try:
                audio_data = np.concatenate(self.resample_buffer)
                if self.current_samplerate != self.target_samplerate:
                    import resampy
                    audio_data = resampy.resample(audio_data, self.current_samplerate, self.target_samplerate)
                self.audio_data.append(audio_data)
                self.resample_buffer = []
            except Exception as e:
                print(f"Error processing final buffer: {e}")
        
        # Get final result
        try:
            if self.audio_data:
                # Combine all audio
                combined_audio = np.concatenate(self.audio_data)
                
                # Save the audio
                timestamp = int(time.time())
                audio_filename = f"sample_{timestamp}.wav"
                filepath = self.sample_dir / audio_filename
                sf.write(filepath, combined_audio, self.target_samplerate)
                print(f"\nSaved audio to {filepath}")
                
                # Process with Whisper
                print("Transcribing with Whisper...")
                result = self.model.transcribe(combined_audio, language="en")
                
                if result["text"].strip():
                    whisper_text = result["text"].strip()
                    print(f"Whisper transcription: {whisper_text}")
                    
                    # Ask for manual correction
                    print("\nPlease review the transcription.")
                    print("1. Accept as is")
                    print("2. Correct it")
                    print("3. Discard this sample")
                    choice = input("Choose an option (1-3): ")
                    
                    if choice == "1":
                        # Accept the transcription as is
                        self.transcriptions[audio_filename] = whisper_text
                        print("Transcription accepted.")
                    elif choice == "2":
                        # Correct the transcription
                        corrected = input(f"Enter corrected text [{whisper_text}]: ") or whisper_text
                        self.transcriptions[audio_filename] = corrected
                        print("Transcription corrected.")
                    elif choice == "3":
                        # Delete the audio file
                        try:
                            os.remove(filepath)
                            print(f"Deleted {filepath}")
                        except Exception as e:
                            print(f"Error deleting file: {e}")
                    else:
                        print("Invalid choice. Keeping audio but not adding transcription.")
                    
                else:
                    print("No text recognized by Whisper.")
                    manual_text = input("Enter correct transcription (or leave empty to discard): ")
                    if manual_text:
                        self.transcriptions[audio_filename] = manual_text
                        print("Manual transcription added.")
                    else:
                        # Delete the audio file
                        try:
                            os.remove(filepath)
                            print(f"Deleted {filepath}")
                        except Exception as e:
                            print(f"Error deleting file: {e}")
                
                # Save updated transcriptions
                self.save_transcriptions()
            else:
                print("No audio data collected")
        except Exception as e:
            print(f"Error processing recording: {e}")
            import traceback
            traceback.print_exc()

def main():
    collector = VoiceSampleCollector()
    
    print("\n===== Voice Sample Collector =====")
    print("This tool helps you create a dataset of voice recordings")
    print("with corresponding transcriptions for model fine-tuning.")
    
    while True:
        print("\n----- Menu -----")
        print("1. Record a new sample")
        print("2. Show collected samples")
        print("3. Exit")
        
        choice = input("Choose an option (1-3): ")
        
        if choice == "1":
            print("\nPress Enter to start recording, and Enter again to stop...")
            input()
            collector.start_recording()
            input()
            collector.stop_recording()
        elif choice == "2":
            # Show collected samples
            if collector.transcriptions:
                print("\n----- Collected Samples -----")
                for filename, text in collector.transcriptions.items():
                    print(f"{filename}: {text}")
                print(f"Total samples: {len(collector.transcriptions)}")
            else:
                print("\nNo samples collected yet.")
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 