# Installation Guide

This guide will help you set up the necessary environment and tools to run the TrustPilot script on your machine.

## Prerequisites

1. **Python Installation:**
   - Ensure that Python 3.11 or later is installed on your machine.
   - You can download the latest version of Python from [Python's official website](https://www.python.org/downloads/).

2. **Browser Installation:**
   - **Brave Browser (Recommended):** It is advised to use Brave Browser for this setup.
   - **Google Chrome (Optional):** If you prefer to use Google Chrome, you will need to modify the configuration later.

## Download and Setup

1. **Download the Project:**
   - Visit the [TrustPilot GitHub Repository](https://github.com/ivasoom/trustpilot).
   - Click on the green "Code" button and select "Download ZIP" to download the project files.

2. **Unzip the Files:**
   - Locate the downloaded ZIP file in your system.
   - Right-click on the file and select "Extract All..." to unzip the file.
   - Navigate to the unzipped folder.

3. **Install Required Libraries:**
   - Open the unzipped folder.
   - Run the `refresh.py` script to automatically install all the necessary Python libraries.

## Running the Script

1. **Start the Script:**
   - In the unzipped folder, find and double-click on the `TrustPilot.bat` file to start the script.

2. **Create a Desktop Shortcut (Optional):**
   - If you want easier access, right-click on the `TrustPilot.bat` file, click show more options and select "Send to" > "Desktop (create shortcut)".
   - This will create a shortcut on your desktop for quick access.

## Configuring for Chrome (Optional)

If you prefer to use Google Chrome instead of Brave Browser:

1. **Copy Configuration File:**
   - In the project folder, find `configSample.ini`.
   - Copy and rename it to `config.ini`.

2. **Modify Configuration:**
   - Open `config.ini` with a text editor (e.g., Notepad).
   - Add the following section to specify the Chrome browser location:

   ```ini
   [Browser]
   location=<Chrome installation path>
   ```

   - Replace `<Chrome installation path>` with the actual path where Chrome is installed on your machine (e.g., `C:\Program Files\Google\Chrome\Application\chrome.exe`).

