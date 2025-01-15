import numpy as np
import os
from pathlib import Path
import time
import pyautogui
import json
from scipy.interpolate import splprep, splev

from record_movements import MouseDataHandler

import random

# Instantiate the MouseDataHandler class
mouse_data_handler = MouseDataHandler(base_dir="mouse_recordings")
print("MouseDataHandler instantiated.", mouse_data_handler.metadata_path)
for rec_id, meta in mouse_data_handler.metadata["recordings"].items():
            print(f"Recording ID: {rec_id}", meta)
recordings = mouse_data_handler.get_all_recordings()
if not recordings:
    print("No recordings found.")
random_recording = random.choice(recordings)
recording_id = random_recording["id"]

print(f"Selected recording: {recording_id}")   
mouse_data_handler.replay_recording(recording_id)
# # Function to replay a randomly chosen recording
# def replay_random_recording():
#     try:
        # mouse_data_handler.load_metadata()

#         # Get all recordings from metadata
#         recordings = mouse_data_handler.get_all_recordings()
        
#         if not recordings:
#             print("No recordings found.")
#             return
        
#         # Randomly select a recording
#         random_recording = random.choice(recordings)
#         recording_id = random_recording["id"]
        
#         print(f"Selected recording: {recording_id}")
        
#         # Replay the selected recording
#         mouse_data_handler.replay_recording(recording_id)
        
#     except Exception as e:
#         print(f"Error: {e}")

# # Call the function to replay a random recording
# replay_random_recording()

