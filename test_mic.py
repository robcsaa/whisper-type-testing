#!/usr/bin/env python3
import sounddevice as sd
import numpy as np
import time

def audio_callback(indata, frames, time, status):
    if status:
        print(f"Status: {status}")
    if np.any(indata):
        print(f"Audio level: {np.abs(indata).mean():.3f}")
        print(f"Audio data: shape={indata.shape}, dtype={indata.dtype}, min={indata.min():.3f}, max={indata.max():.3f}")

def main():
    print("Available devices:")
    print(sd.query_devices())
    
    # Find PipeWire device
    devices = sd.query_devices()
    mic_device = None
    for i, device in enumerate(devices):
        if 'pipewire' in device['name'].lower():
            mic_device = i
            print(f"Found PipeWire device: {device['name']}")
            break
    
    if mic_device is None:
        print("No PipeWire device found, using default input device")
        mic_device = sd.default.device[0]
    
    device_info = sd.query_devices(mic_device)
    print(f"\nUsing device: {device_info['name']}")
    print(f"Device info: {device_info}")
    
    try:
        with sd.InputStream(device=mic_device,
                          samplerate=int(device_info['default_samplerate']),
                          channels=1,
                          dtype='float32',
                          callback=audio_callback,
                          blocksize=1024,
                          latency='low') as stream:
            print("\nRecording started. Speak into your microphone...")
            print("Press Ctrl+C to stop")
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nRecording stopped")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 