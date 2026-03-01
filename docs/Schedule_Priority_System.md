# NPC Schedule Priority & Interaction System

## Overview
The Schedule Priority System assigns a priority level (1-5) to every action in an NPC's daily schedule. This priority determines how the NPC responds to interruptions from Players and other NPCs.

This system ensures that NPCs behavior aligns with their current context—sleeping NPCs cannot chat, working NPCs stay focused, and idle NPCs are open to interaction.

## Priority Levels (1-5)

| Priority | Level | Description | Behavior Rule | Examples |
| :--- | :--- | :--- | :--- | :--- |
| **5** | **Critical** | Uninterruptible | **Silent / Action Only**. Rejects all interaction. | Sleeping, Coma, Deep Meditation, Scripted Cutscene. |
| **4** | **High** | Task Focused | **Restricted**. Rejects casual chat. Accepts only task-related interaction. | Important Meeting, Combat, Focused Work, Urgent Quest. |
| **3** | **Normal** | Routine | **Standard**. Can be interrupted but prefers current task. | Eating, Chores, Routine Job, Shopping. |
| **2** | **Low** | Open | **Flexible**. Happy to be interrupted. | Wandering, Resting, Hobbies, Watching TV. |
| **1** | **Idle** | Bored | **Seeking**. Actively looks for interaction. | Doing nothing, Waiting, Bored. |

---

## Interaction Logic

### 1. Player-NPC Interaction (`PlayerEngine`)

When a Player talks to an NPC:
1.  **Check Priority**: The system retrieves the NPC's current schedule item.
2.  **Context Injection**: The Priority and Action are injected into the LLM Prompt.
3.  **Reaction Decision**:
    *   **Priority 5**: NPC must NOT speak. Returns an `action` description (e.g., `*Continues sleeping soundly*`).
    *   **Priority 4**: NPC may express annoyance or polite refusal ("I'm busy"). If the Player offers something valuable or has high affinity, the NPC *might* accept.
    *   **Priority < 4**: Normal conversation.
4.  **Schedule Modification**:
    *   The NPC can decide to **modify their schedule** based on the conversation (e.g., agreeing to a date).
    *   The system supports `schedule_modification` output to insert or overwrite events.

### 2. NPC-NPC Social Interaction (`SocialEngine`)

When two or more NPCs are in the same location:

#### Logic Flow
1.  **Priority Scan**: Check the priority of all participants.
2.  **Rule 1: Critical Silence (The "Sleep" Filter)**
    *   If **ANY** participant has **Priority 5**, the social event is **SKIPPED**. (Silence prevails).
3.  **Rule 2: Mixed Priority Block**
    *   If some participants are **High (4)** and others are **Low (<4)**, the social event is **SKIPPED**. (Busy people ignore idlers).
4.  **Rule 3: Task Resonance (The "Meeting" Mode)**
    *   If **ALL** participants are **High (4)**:
        *   **ALLOWED**, but entered in **`task_focused` Mode**.
        *   **Constraint**: Dialogue must strictly relate to the `Current Action`. No casual chat.
5.  **Rule 4: Casual Chat**
    *   If **ALL** participants are **Low/Normal (<4)**:
        *   **ALLOWED** in **`casual` Mode**.
        *   Standard topics (Hobbies, Gossip, Weather).

---

## Prompt Engineering

### Scheduler Prompt (`scheduler.py`)
Responsible for generating the `priority` field in the JSON schedule.
- Instructions added to assign 5 for Sleep, 4 for Work, etc.

### Reaction Prompt (`reaction.py`)
Responsible for Player interactions.
- **Layer 0**: Checks Priority 5 (Silence rule).
- **Output**: Supports `schedule_modification` JSON field.

### Social Prompt (`social.py`)
Responsible for NPC-NPC interactions.
- **Input**: Receives `Social Mode` ('casual' vs 'task_focused').
- **Layer 0**: Enforces topic constraints based on mode.

---

## Data Structure

### Schedule Item
```json
{
  "time": "08:00",
  "action": "work",
  "description": "Opens the weapon shop",
  "location": "Shop",
  "priority": 4,           // Int: 1-5
  "allow_interruption": false // Bool: Explicit override (optional)
}
```

### Schedule Modification Output
```json
{
  "schedule_modification": {
      "type": "add", // or "update"
      "event": {
          "time": "12:00",
          "action": "lunch_date",
          "location": "Restaurant",
          "priority": 4
      }
  }
}
```
