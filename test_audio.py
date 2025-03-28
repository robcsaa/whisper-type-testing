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

def test_device(device_id, device_info):
    print(f"\nTesting device: {device_info['name']}")
    print(f"Device info: {device_info}")
    
    try:
        with sd.InputStream(device=device_id,
                          samplerate=int(device_info['default_samplerate']),
                          channels=1,
                          dtype='float32',
                          callback=audio_callback,
                          blocksize=1024,
                          latency='low') as stream:
            print(f"Stream opened successfully: {stream}")
            print("Recording for 5 seconds...")
            time.sleep(5)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Available devices:")
    print(sd.query_devices())
    
    # Test each input device
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:  # Only test input devices
            test_device(i, device)

if __name__ == "__main__":
    main() 