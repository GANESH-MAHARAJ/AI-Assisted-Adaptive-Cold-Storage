import pandas as pd
import plotly.express as px

# Define project tasks with durations
tasks = [
    {"Task": "Requirement Analysis", "Start": "2025-08-01", "Finish": "2025-08-15"},
    {"Task": "Prototype Hardware Setup", "Start": "2025-08-16", "Finish": "2025-09-05"},
    {"Task": "Backend Development (Flask + MongoDB)", "Start": "2025-09-06", "Finish": "2025-09-20"},
    {"Task": "AI Agent Integration", "Start": "2025-09-21", "Finish": "2025-10-05"},
    {"Task": "Dashboard Development", "Start": "2025-10-06", "Finish": "2025-10-20"},
    {"Task": "Plotly Visualization App", "Start": "2025-10-21", "Finish": "2025-11-05"},
    {"Task": "System Integration & Testing", "Start": "2025-11-06", "Finish": "2025-11-20"},
    {"Task": "Documentation & Report Writing", "Start": "2025-11-21", "Finish": "2025-12-01"},
]

df = pd.DataFrame(tasks)

# Create Gantt chart
fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", title="Adaptive Cooling System Project Gantt Chart",
                  color="Task")
fig.update_yaxes(autorange="reversed")  # Reverse so tasks are in order
fig.show()
