import numpy as np
import os
from pathlib import Path
import time
import pyautogui
import json
from scipy.interpolate import splprep, splev

class MouseDataHandler:
    def __init__(self, base_dir="mouse_recordings"):
        """Initialize the data handler with a base directory for recordings"""
        self.base_dir = Path(base_dir)
        
        self.base_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different data types
        self.recordings_dir = self.base_dir / "recordings"
        self.recordings_dir.mkdir(exist_ok=True)
        
        # Initialize metadata file
        self.metadata_path = self.base_dir / "metadata.json"
        self.load_metadata()

    def load_metadata(self):
        """Load metadata from JSON file or create new if doesn't exist"""
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {"recordings": {}}
            self.save_metadata()

    def save_metadata(self):
        """Save metadata to JSON file"""
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def save_recording(self, positions_array, session_id, movement_num):
        """Save a single recording as a numpy file"""
        # Create filename with session and movement info
        filename = f"recording_{session_id}_{movement_num:03d}.npy"
        filepath = self.recordings_dir / filename
        
        # Save the numpy array
        np.save(filepath, positions_array)
        
        # Update metadata
        recording_id = f"{session_id}_{movement_num:03d}"
        self.metadata["recordings"][recording_id] = {
            "filename": filename,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_points": len(positions_array),
            "duration": len(positions_array) * 0.01  # Assuming 100Hz recording
        }
        self.save_metadata()
        
        return recording_id

    def load_recording(self, recording_id):
        """Load a specific recording by its ID"""
        if recording_id not in self.metadata["recordings"]:
            raise ValueError(f"Recording {recording_id} not found")
            
        filename = self.metadata["recordings"][recording_id]["filename"]
        filepath = self.recordings_dir / filename
        return np.load(filepath)

    def get_all_recordings(self):
        """Get list of all recordings with their metadata"""
        recordings = []
        for rec_id, meta in self.metadata["recordings"].items():
            recordings.append({
                "id": rec_id,
                "timestamp": meta["timestamp"],
                "num_points": meta["num_points"],
                "duration": meta["duration"]
            })
        return sorted(recordings, key=lambda x: x["timestamp"])

    def export_recordings_info(self):
        """Export information about all recordings"""
        recordings = self.get_all_recordings()
        total_points = sum(rec["num_points"] for rec in recordings)
        total_duration = sum(rec["duration"] for rec in recordings)
        
        print("\nRecordings Summary:")
        print(f"Total recordings: {len(recordings)}")
        print(f"Total points: {total_points}")
        print(f"Total duration: {total_duration:.2f} seconds")
        print("\nIndividual Recordings:")
        
        for rec in recordings:
            print(f"\nID: {rec['id']}")
            print(f"Timestamp: {rec['timestamp']}")
            print(f"Points: {rec['num_points']}")
            print(f"Duration: {rec['duration']:.2f} seconds")

    def replay_recording(self, recording_id, speed_factor=1.0):
        """Replay a specific recording with speed adjustment"""
        try:
            positions = self.load_recording(recording_id)
            
            # Get starting position for relative movement
            start_x, start_y = pyautogui.position()
            first_x, first_y = positions[0]
            offset_x = start_x - first_x
            offset_y = start_y - first_y
            
            print(f"Replaying recording {recording_id}")
            print("Move mouse to corner to stop replay")
            
            time.sleep(2)  # Give user time to prepare
            
            for x, y in positions:
                pyautogui.moveTo(
                    int(x + offset_x),
                    int(y + offset_y),
                    duration=0.01/speed_factor
                )
                
        except pyautogui.FailSafeException:
            print("Replay stopped - mouse moved to corner")
        except Exception as e:
            print(f"Error during replay: {e}")
    def demo_usage(self):
        """Demonstrate how to use the MouseDataHandler"""
        
        while True:
            print("\nMouse Recording Data Handler")
            print("1. List all recordings")
            print("2. Replay a recording")
            print("3. Export recordings info")
            print("4. Exit")
            
            choice = input("Choose option (1-4): ")
            
            if choice == "1":
                recordings = self.get_all_recordings()
                if not recordings:
                    print("No recordings found")
                    continue
                    
                print("\nAvailable Recordings:")
                for i, rec in enumerate(recordings, 1):
                    print(f"{i}. Recording {rec['id']}")
                    print(f"   Recorded: {rec['timestamp']}")
                    print(f"   Points: {rec['num_points']}")
                    print(f"   Duration: {rec['duration']:.2f}s")
                    
            elif choice == "2":
                recordings = self.get_all_recordings()
                if not recordings:
                    print("No recordings found")
                    continue
                    
                print("\nAvailable Recordings:")
                for i, rec in enumerate(recordings, 1):
                    print(f"{i}. Recording {rec['id']}")
                
                try:
                    idx = int(input("Choose recording number: ")) - 1
                    if 0 <= idx < len(recordings):
                        speed = float(input("Replay speed factor (1.0 = normal): "))
                        self.replay_recording(recordings[idx]["id"], speed)
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Invalid input")
                    
            elif choice == "3":
                self.export_recordings_info()
                
            elif choice == "4":
                break
                
            else:
                print("Invalid choice")

def demo_usage():
    """Demonstrate how to use the MouseDataHandler"""
    handler = MouseDataHandler()
    
    while True:
        print("\nMouse Recording Data Handler")
        print("1. List all recordings")
        print("2. Replay a recording")
        print("3. Export recordings info")
        print("4. Exit")
        
        choice = input("Choose option (1-4): ")
        
        if choice == "1":
            recordings = handler.get_all_recordings()
            if not recordings:
                print("No recordings found")
                continue
                
            print("\nAvailable Recordings:")
            for i, rec in enumerate(recordings, 1):
                print(f"{i}. Recording {rec['id']}")
                print(f"   Recorded: {rec['timestamp']}")
                print(f"   Points: {rec['num_points']}")
                print(f"   Duration: {rec['duration']:.2f}s")
                
        elif choice == "2":
            recordings = handler.get_all_recordings()
            if not recordings:
                print("No recordings found")
                continue
                
            print("\nAvailable Recordings:")
            for i, rec in enumerate(recordings, 1):
                print(f"{i}. Recording {rec['id']}")
            
            try:
                idx = int(input("Choose recording number: ")) - 1
                if 0 <= idx < len(recordings):
                    speed = float(input("Replay speed factor (1.0 = normal): "))
                    handler.replay_recording(recordings[idx]["id"], speed)
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")
                
        elif choice == "3":
            handler.export_recordings_info()
            
        elif choice == "4":
            break
            
        else:
            print("Invalid choice")

if __name__ == "__main__":
    demo_usage()