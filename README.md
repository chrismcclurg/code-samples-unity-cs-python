# Code Samples (Unity / C# / Python)

This repository contains a small set of code samples demonstrating real-time communication between Unity (C#) and Python, along with basic robot behavior logic and a simple ML-based shooter-trajectory prediction pipeline.

These files are extracted from a larger VR simulation platform developed for my PhD dissertation. In that work, more than 300 human participants role-played as school shooters in VR while autonomous robots attempted to delay or disrupt them. The code shared here illustrates the communication and prediction components used in those experiments.

## Contents

### C# (Unity)

**ShooterPredictor.cs**  
Sends simulation state from Unity to Python using UDP and receives predicted trajectories. Includes:
- Socket setup (send/receive)
- Threaded message handling
- Data packaging for prediction inputs
- Parsing and visualizing predicted world positions

**ControlRobot.cs**  
Implements simple autonomous robot behavior using Unity NavMesh. Includes:
- Behavior selection (rest, follow, race, search)
- Visibility checks via Physics.Linecast
- NavMeshAgent control
- Integration of predicted positions from ShooterPredictor

---

### Python

**main.py**  
Receives Unity state, prepares model inputs, runs a prediction model, and returns future trajectory points.

**functions.py**  
Helper functions for coordinate transforms, occupancy-grid construction, step history, and preparing model inputs.

---

## Notes

- These scripts reference other components from the full project (e.g., `SchoolManager`, `CheckFocusObject`). They are included as code samples only.
- The models and larger Unity project are not required to understand the code structure.
- Additional context can be provided!
