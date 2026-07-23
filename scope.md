# Watch – Project Handover

## Overview

**Watch** is an MCP (Model Context Protocol) server that gives AI coding agents the ability to **watch and understand videos**.

Current coding agents like **Claude Code**, **Codex**, and **Cursor** excel at reasoning over text, code, and images, but they are effectively blind to videos. Developers frequently share bugs, feature walkthroughs, tutorials, and UI demonstrations as screen recordings. **Watch** bridges that gap.

The core philosophy is:

> **AI coding agents already have the brain. Watch gives them eyes.**

Watch analyzes videos and returns structured observations that AI agents can reason over, allowing them to answer questions about what happened in the recording.

---

# Problem

AI coding agents currently understand:

* Text
* Code
* Images
* Files

They generally **cannot directly understand videos**.

Developers constantly share:

* Loom recordings
* ScreenPal recordings
* Screen Studio recordings
* Browser recordings
* OBS recordings
* Mobile recordings
* Bug reproductions
* Feature demos
* Tutorial videos

Today these videos are almost unusable by coding agents.

---

# Goal

Allow workflows like:

```
User:

Why is my React modal closing?

[bug.mp4]
```

Claude Code should automatically invoke Watch.

Watch analyzes the recording and returns structured context.

Claude then answers using that context.

---

# Product Vision

Watch acts as the **visual perception layer** for AI agents.

```
Video

↓

Watch

↓

Structured observations

↓

Claude Code

↓

Reasoning
```

The coding agent remains responsible for reasoning.

Watch is responsible for perception.

---

# High-Level Architecture

```
                  User

                    │

                    ▼

              Claude Code

                    │

          invokes MCP tool

                    │

                    ▼

                Watch MCP

                    │

         Video Understanding Layer

                    │

     Video Model + OCR + Processing

                    │

                    ▼

         Structured Timeline JSON

                    │

                    ▼

              Claude Code

                    │

                    ▼

         Final reasoning & answer
```

---

# MVP Inputs

## Local video files

Examples

```
bug.mp4

demo.mov

recording.webm
```

---

## Local screen recordings

Examples

```
Desktop Recording.mp4

QuickTime Recording.mov

OBS Recording.mp4
```

---

## Hosted recording URLs

Support URLs from platforms such as:

* Loom
* ScreenPal
* Screen Studio
* Vimeo (public)
* Direct MP4 links

Example

```python
watch_video(
    url="https://loom.com/share/..."
)
```

The MCP downloads the video temporarily, analyzes it, and deletes it after processing.

---

# Future Inputs

## Live screen sharing

Eventually support:

```
Live Screen

↓

Watch

↓

Continuous observations

↓

Claude Code
```

Example observations:

```
00:02
VS Code opens.

00:08
Developer opens app.ts

00:15
Browser console displays TypeError

00:21
Developer refreshes browser

00:28
Modal disappears
```

The AI agent continuously gains awareness of what is happening on the screen.

---

# Primary MCP Tool

Initial tool:

```python
watch_video()
```

Examples

```python
watch_video(
    path="bug.mp4",
    prompt="Why does the modal disappear?"
)
```

or

```python
watch_video(
    url="https://loom.com/share/..."
)
```

---

# Output Format

Do **not** describe every frame.

Instead return meaningful events.

Example:

```json
{
  "duration": "02:13",
  "events": [
    {
      "timestamp": "00:05",
      "type": "navigation",
      "description": "Developer opens localhost:3000"
    },
    {
      "timestamp": "00:18",
      "type": "interaction",
      "description": "Clicks Submit button"
    },
    {
      "timestamp": "00:22",
      "type": "error",
      "description": "Browser console displays HTTP 500"
    }
  ]
}
```

Claude Code reasons over these events.

---

# Important Design Principle

Avoid:

```
Describe every second.
```

That creates:

* Massive outputs
* High token costs
* Context window waste
* Redundant information

Instead produce **semantic observations**.

Examples:

* Page navigation
* User interaction
* UI changes
* Console errors
* Terminal output
* Network failures
* Loading states
* Dialog open/close
* Code editor activity

Watch should compress video into useful context.

---

# Proposed Processing Pipeline

```
Video

↓

Scene detection

↓

Frame sampling

↓

OCR

↓

Video understanding model

↓

Event extraction

↓

Timeline generation

↓

Claude Code
```

---

# Primary Use Cases

### Bug reproduction

```
Why is this happening?
```

---

### UI implementation

```
Implement this interface shown in the recording.
```

---

### Product walkthroughs

```
Build this feature demonstrated in the video.
```

---

### Tutorial videos

```
Extract the implementation steps.
```

---

### QA

```
Generate reproduction steps from this recording.
```

---

# Future MCP Tools

```
watch_video()

find_bug()

summarize_video()

extract_ui_flow()

extract_code()

find_timestamp()

answer_video_question()

watch_live_screen()
```

---

# Models

The implementation should remain model-agnostic.

Initial candidates:

* Xiaomi MiMo
* Alibaba Qwen2.5-VL

The provider should be replaceable without changing the MCP interface.

---

# Tech Stack

### Backend

* Python
* FastAPI
* MCP Python SDK

### Video Processing

* FFmpeg
* OpenCV

### OCR

* PaddleOCR or equivalent

### Deployment

* Docker
* Oracle Cloud Free Tier (MVP)

### Storage

Temporary only.

Videos are deleted after processing.

---

# Future Roadmap

## Phase 1

* Local video files
* Loom URLs
* ScreenPal URLs
* Structured timeline output

## Phase 2

* Better OCR
* Audio transcription
* Terminal understanding
* Browser understanding
* Search within videos

## Phase 3

* Live screen sharing
* Continuous perception
* Real-time observations
* Streaming events to Claude Code

---

# Product Philosophy

Watch is **not another AI assistant**.

It does not replace Claude Code, Codex, or Cursor.

It extends them.

Current coding agents have:

* ✅ Reasoning
* ✅ Planning
* ✅ Coding
* ❌ Visual perception

Watch provides that missing perception layer by transforming videos and, eventually, live screens into structured context that AI agents can understand and act upon.
