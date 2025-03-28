#!/usr/bin/env python3
import psutil
import subprocess
import os
import json

def get_gpu_info():
    try:
        # Try to get NVIDIA GPU info using nvidia-smi
        nvidia_smi = subprocess.check_output(['nvidia-smi', '--query-gpu=gpu_name,memory.total,memory.used', '--format=csv,noheader'])
        return nvidia_smi.decode().strip()
    except:
        return "No NVIDIA GPU detected"

def get_system_info():
    cpu_count = psutil.cpu_count()
    memory = psutil.virtual_memory()
    gpu_info = get_gpu_info()
    
    return {
        "cpu_cores": cpu_count,
        "total_memory_gb": round(memory.total / (1024**3), 2),
        "available_memory_gb": round(memory.available / (1024**3), 2),
        "gpu_info": gpu_info
    }

def recommend_model(system_info):
    # RTX 3060 Mobile has 6GB VRAM
    if "RTX 3060" in system_info["gpu_info"]:
        return {
            "recommended_model": "vosk-model-en-us-0.22",
            "reason": "Your RTX 3060 Mobile GPU has sufficient VRAM to handle the larger model, which provides better accuracy.",
            "model_size": "1.8GB",
            "download_url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
        }
    else:
        return {
            "recommended_model": "vosk-model-small-en-us-0.15",
            "reason": "Using the small model as default for compatibility.",
            "model_size": "40MB",
            "download_url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        }

def main():
    print("Running system check...")
    system_info = get_system_info()
    model_recommendation = recommend_model(system_info)
    
    print("\nSystem Information:")
    print(f"CPU Cores: {system_info['cpu_cores']}")
    print(f"Total Memory: {system_info['total_memory_gb']}GB")
    print(f"Available Memory: {system_info['available_memory_gb']}GB")
    print(f"GPU: {system_info['gpu_info']}")
    
    print("\nModel Recommendation:")
    print(f"Recommended Model: {model_recommendation['recommended_model']}")
    print(f"Model Size: {model_recommendation['model_size']}")
    print(f"Reason: {model_recommendation['reason']}")
    
    # Save the information to a JSON file for the FAQ
    with open('system_info.json', 'w') as f:
        json.dump({
            "system_info": system_info,
            "model_recommendation": model_recommendation
        }, f, indent=4)

if __name__ == "__main__":
    main() 