# Code Samples (Unity / C# / Python)

This repository contains a small set of code samples showing real-time communication between Unity (C#) and Python, basic robot behavior logic, and a simple machine-learning prediction pipeline.

These files are extracted from a larger VR simulation project. They are included to demonstrate software engineering practices, modular design, and non-trivial interactions between systems.

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
Utility functions for coordinate transforms, occupancy-grid construction, step history, and preparing model inputs.

---

## Notes

- These scripts reference other components from the full project (e.g., `SchoolManager`, `CheckFocusObject`). They are included as code samples only.
- The models and larger Unity project are not required to understand the code structure.
- Additional context or sample writing can be provided on request.
