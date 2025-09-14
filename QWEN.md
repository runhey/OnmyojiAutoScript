# OnmyojiAutoScript (OAS) - Project Context

## Project Overview

**OnmyojiAutoScript (OAS)** is an automation script for the mobile game "Onmyoji" (阴阳师), designed to automate various in-game tasks to reduce player effort. The project is built with Python and provides both a command-line interface and a graphical user interface.

### Key Features
- Automates daily tasks like demon encounters, realm raids, exploration, Orochi battles, and more
- Supports both solo and multiplayer modes for various activities
- Includes a rich configuration system with many customization options
- Provides a GUI built with Qt/FluentUI for easy configuration and monitoring
- Uses computer vision and OCR for game state recognition
- Works with Android emulators via ADB

### Technologies Used
- **Language**: Python 3.10+
- **GUI Framework**: PySide6 (Qt) with QML for FluentUI
- **Computer Vision**: OpenCV
- **OCR**: PaddleOCR (via ppocr-onnx)
- **Device Control**: ADB (Android Debug Bridge)
- **Configuration**: Pydantic for type-safe configuration management
- **Networking**: ZeroRPC for inter-process communication
- **Web Framework**: FastAPI for web-based interfaces

## Project Structure

```
OnmyojiAutoScript/
├── config/                 # Configuration templates and i18n files
├── module/                 # Core modules (device control, GUI, OCR, etc.)
│   ├── base/               # Base classes and utilities
│   ├── config/             # Configuration management
│   ├── device/             # Device connection and control
│   ├── gui/                # Graphical user interface
│   ├── ocr/                # Optical character recognition
│   └── ...
├── tasks/                  # Individual automation tasks
│   ├── Orochi/             # Orochi (八岐大蛇) automation
│   ├── RealmRaid/          # Realm raid automation
│   ├── Exploration/        # Exploration automation
│   └── ...                 # Many other task modules
├── fluentui/               # FluentUI resources
└── ...
```

## Core Components

### 1. Task System
The project is organized around modular tasks, each representing a specific in-game activity:
- Each task is in its own directory under `tasks/`
- Tasks inherit from base classes that provide common functionality
- Configuration is defined using Pydantic models
- Tasks can be enabled/disabled and scheduled through the config

### 2. Device Management
- Connects to Android devices/emulators via ADB
- Handles screenshot capture and input simulation
- Supports multiple screenshot methods (ADB, Scrcpy, etc.)
- Manages app start/stop operations

### 3. GUI System
- Built with Qt/FluentUI for a modern interface
- Uses QML for UI layout and design
- Communicates with the backend via ZeroRPC
- Allows real-time monitoring and configuration

### 4. Configuration
- Centralized configuration system using JSON templates
- Pydantic models for type validation
- Extensive customization options for each task
- Support for multiple configuration profiles

## Development Setup

### Prerequisites
- Python 3.10+
- Android emulator or device with ADB enabled
- Required Python packages listed in `requirements.txt`

### Installation Steps
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure the script by editing JSON config files or using the GUI

### Running the Application
- GUI mode: `python gui.py`
- Script mode: `python script.py`
- Server mode: `python server.py`

## Key Development Concepts

### Task Implementation
Tasks are implemented by creating a `ScriptTask` class that inherits from relevant base classes:
- `GeneralBattle` for combat-related functionality
- `GeneralInvite` for team invitation mechanics
- `SwitchSoul` for御魂 switching
- Task-specific asset definitions for image recognition

### Device Interaction
The `Device` class handles all interactions with the Android device:
- Screenshot capture and processing
- Touch input simulation
- App lifecycle management
- Stuck detection and error handling

### GUI Architecture
The GUI uses a context-based approach:
- Context objects provide data and functions to QML
- Bridge pattern for communication between Python backend and QML frontend
- FluentUI components for consistent design language

## Common Development Patterns

1. **Inheritance Chain**: Tasks inherit from multiple base classes to compose functionality
2. **Configuration-Driven**: All behavior is controlled through configuration files
3. **Image Recognition**: Uses template matching and OCR for game state detection
4. **State Machine**: Tasks follow defined state transitions based on UI elements
5. **Error Handling**: Comprehensive exception handling with automatic recovery

## Testing and Debugging

- Use the GUI to monitor real-time execution
- Check logs in the `log/` directory for debugging information
- Use development tools in the `dev_tools/` directory
- Enable debug options in configuration for detailed output

## Contribution Guidelines

- Follow the existing code structure and patterns
- Use type hints for all function signatures
- Write clear docstrings for complex functions
- Test changes thoroughly with the target emulator/device
- Follow the project's naming conventions (snake_case for files/variables, PascalCase for classes)

## Useful Resources

- Documentation: https://runhey.github.io/OnmyojiAutoScript-website/
- Main repository: https://github.com/runhey/OnmyojiAutoScript
- Related projects: Based on Alas (AzurLaneAutoScript) framework

## Important Notes

1. This script is for educational purposes only
2. Use at your own risk - automated gameplay may violate game terms of service
3. The project is licensed under GNU General Public License v3.0
4. Keep the script updated to maintain compatibility with game changes