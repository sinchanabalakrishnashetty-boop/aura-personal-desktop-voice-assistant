# Aura - Personal Desktop Voice Assistant

Aura is a Python desktop assistant for Windows. It combines a PyQt6 interface,
voice input and output, natural-language command routing, and desktop
automation. Optional integrations add AI-generated responses, Gmail, Google
Contacts, and wake-word detection.

## Project goals

- Make everyday desktop tasks accessible through voice or text commands.
- Provide speech recognition and spoken responses through a desktop UI.
- Launch applications, work with files, and open web searches.
- Offer optional AI and Google-service integrations.
- Keep account, interaction, and preference data locally.

## Features

### Voice and conversation

- Capture microphone input and send it to Google Speech Recognition.
- Retry recognition using the `en-IN` locale if the `en-US` attempt does not
  recognize speech.
- Convert responses to speech with `pyttsx3`.
- Select a voice based on English or Kannada text when a matching system voice
  is installed.
- Listen for the wake phrase "Hey Aura." Porcupine can be used with a configured
  keyword file; otherwise the wake listener uses SpeechRecognition.
- Use a rule-based intent and entity parser, selected fuzzy command matching,
  and an optional intent-routing pipeline.

The `models/vosk-small-en/` directory contains a Vosk English model, but the
current voice-capture flow in `aura_panel.py` uses Google Speech Recognition;
the Vosk model is not wired into that flow.

### Assistant commands

- Open and close applications using Windows Start Menu shortcuts, installed
  executable discovery, and known aliases.
- Create, read, edit, list, search, open, copy, move, rename, and delete files
  and folders.
- Open Google, YouTube, and Wikipedia searches and answer selected common
  questions using built-in responses.
- Open Spotify and automate selected search and playback interactions.
- Report the current time and date; route supported weather and news requests
  to online sources or apps.
- Request supported system actions, such as locking, sleep, shutdown, restart,
  or signing out. Selected sensitive commands use permission checks or
  confirmation.
- Start an email-drafting conversation, resolve contacts when configured, and
  send through Gmail API or SMTP when configured.
- Prepare WhatsApp messages in a native or web compose flow for the user to
  review and send manually.
- Read on-screen text using OCR through a separate screen-reader helper.

Desktop automation depends on Windows configuration and installed software.
For example, the current Windows volume handler requires NirCmd; brightness
control is not implemented for Windows in the current command handler.

### User interface and storage

- PyQt6 login and registration screens, assistant panel, conversation display,
  voice controls, status indicators, and optional system tray controls.
- SQLite storage for user accounts and command history.
- JSON files for local memory, preferences, and integration settings.
- Optional Windows startup-at-logon task and desktop shortcut.

## Technology stack

| Area | Technologies used |
|---|---|
| Language and desktop UI | Python, PyQt6 |
| Voice input | SpeechRecognition, PyAudio, sounddevice, NumPy |
| Speech output | pyttsx3 |
| Intent processing | Project-specific regex/keyword rules, fuzzy matching, optional routing pipeline |
| AI responses | OpenAI API and Google Generative AI (optional) |
| Web and knowledge | requests, Wikipedia |
| Desktop automation | PyAutoGUI, Pyperclip, psutil, pywin32, comtypes |
| Google services | google-auth, google-auth-oauthlib, google-api-python-client |
| Email | Gmail API and optional SMTP |
| Local data | SQLite, JSON, python-dotenv |
| OCR and images | Pillow, pytesseract |
| Tray and wake word | pystray, pvporcupine |
| Packaging | PyInstaller, PowerShell build and install scripts |

The Python dependencies and their declared versions are listed in
[`requirements.txt`](requirements.txt). PyInstaller is installed by the build
script.

## Architecture and request flow

1. `run.py` creates the Qt application and initializes login or the main window.
2. The user enters a command by typing or speaking it in the assistant panel.
3. Voice capture records one utterance and SpeechRecognition converts it to
   text. The wake-word listener can open the panel and start that capture.
4. The command engine normalizes and routes the request. Depending on the
   request, it can call local skills, open a web search, run an email workflow,
   or request an AI response.
5. The assistant displays a response and may speak it with pyttsx3.
6. User and assistant turns are written to local SQLite history; selected
   preferences and usage memory are stored as JSON.

## Main modules

| Module | Responsibility |
|---|---|
| [`run.py`](run.py) | Application startup, login restoration, wake listener, tray startup, and shutdown |
| [`aura_panel.py`](aura_panel.py) | Main PyQt6 interface, voice capture, and conversation handling |
| [`aura_login.py`](aura_login.py) | Login, registration, and saved-user flow |
| [`auth.py`](auth.py) | Account validation, registration, login, and password hashing |
| [`db.py`](db.py) | SQLite connection setup |
| [`history.py`](history.py) | Asynchronous SQLite interaction-history writes |
| [`aura/command_engine.py`](aura/command_engine.py) | Main command execution and routing |
| [`aura/enhanced_nlp.py`](aura/enhanced_nlp.py) | Rule-based intent and entity extraction |
| [`aura/intelligence_stack.py`](aura/intelligence_stack.py) | Input normalization, confidence, clarification, and routing support |
| [`aura/fuzzy_matcher.py`](aura/fuzzy_matcher.py) | Matching selected command variations and typos |
| [`aura/voice.py`](aura/voice.py) | Text-to-speech and voice selection |
| [`aura/wake_word.py`](aura/wake_word.py) | Background "Hey Aura" detection |
| [`aura/mic_fix.py`](aura/mic_fix.py) | Microphone capture with PyAudio and sounddevice paths |
| [`aura/skills/apps.py`](aura/skills/apps.py) | Windows application discovery and launch |
| [`aura/skills/filesystem.py`](aura/skills/filesystem.py) | File and folder operations |
| [`aura/email_workflow.py`](aura/email_workflow.py) | Interactive email drafting and sending |
| [`aura/gmail_service.py`](aura/gmail_service.py) | Optional Gmail API sending |
| [`aura/google_contacts.py`](aura/google_contacts.py) | Optional Google Contacts lookup |
| [`aura/music_handler.py`](aura/music_handler.py) | Spotify launch and selected playback automation |
| [`aura/memory_store.py`](aura/memory_store.py) | JSON preferences and usage memory |
| [`aura/screen_reader.py`](aura/screen_reader.py) | Screen capture, OCR, and spoken text |
| [`aura/tray_app.py`](aura/tray_app.py) | System tray show, hide, and exit controls |
| [`project_tools.py`](project_tools.py) | Microphone, OAuth token, and legacy database utilities |

## Repository layout

```text
aura_project/
├── run.py
├── aura_panel.py
├── aura_login.py
├── auth.py
├── db.py
├── history.py
├── project_tools.py
├── requirements.txt
├── aura_config.json
├── .env.example
├── build_desktop.ps1
├── install_windows.ps1
├── startup_task.ps1
├── tune_wake_word.ps1
├── assets/
├── aura/
│   ├── command_engine.py
│   ├── enhanced_nlp.py
│   ├── intelligence_stack.py
│   ├── voice.py
│   ├── wake_word.py
│   ├── mic_fix.py
│   ├── memory_store.py
│   ├── email_workflow.py
│   ├── gmail_service.py
│   ├── google_contacts.py
│   ├── music_handler.py
│   ├── screen_reader.py
│   ├── tray_app.py
│   └── skills/
│       ├── apps.py
│       └── filesystem.py
├── data/
└── models/
    └── vosk-small-en/
```

This tree lists the main source files and omits generated files, local databases,
and private credentials.

## Installation and first run

### Requirements

- Windows
- Python 3.x and pip
- A microphone for voice input
- Internet access for Google speech recognition and optional online services
- Tesseract installed separately if using OCR

### Install Python dependencies

From PowerShell in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configure optional services

Copy `.env.example` to `.env` and add only the settings needed for your setup.
Examples include AI API keys, email sender settings, microphone selection, and
Google integration paths. OAuth-based Google features also require a Google
client credentials file and an authorized token with the required scopes.

Do not commit `.env`, OAuth credentials, tokens, passwords, or other secrets.
Keep real credentials out of source files and shared builds.

### Run Aura

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

When a user is logged in and the wake listener is enabled, say "Hey Aura" to
open the panel and start a command capture. Set `AURA_DISABLE_WAKE=1` in the
environment to disable the wake listener. Set `AURA_CONTINUOUS_VOICE=1` to
enable continuous voice mode in the panel.

## Windows desktop build and install

### Build

```powershell
.\.venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process Bypass
.\build_desktop.ps1
```

The build script uses PyInstaller and normally creates an onedir build at
`dist\Aura\Aura.exe`.

### Install

```powershell
.\.venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1
```

The installer copies the executable under `%LOCALAPPDATA%\AuraDesktop`, creates
a desktop shortcut, and enables startup at logon. Review included data and
credentials before distributing a packaged build.

### Control startup at logon

```powershell
.\startup_task.ps1 -Action enable
.\startup_task.ps1 -Action disable
```

## Wake-word configuration

Choose a microphone profile:

```powershell
.\tune_wake_word.ps1 default
.\tune_wake_word.ps1 quiet-room
.\tune_wake_word.ps1 noisy-room
.\tune_wake_word.ps1 far-field
```

The script updates wake-listener values in `.env`. To choose a microphone on a
system with multiple inputs, set `AURA_WAKE_MIC_INDEX=<device_index>`.

For Porcupine keyword-file detection, set `AURA_WAKE_KEYWORD_PATH` to a
compatible `.ppn` file. Without a custom keyword file, the implementation uses
the SpeechRecognition fallback to detect the wake phrase.

Other wake-listener settings include:

- `AURA_WAKE_ENERGY_THRESHOLD`: energy threshold for microphone input.
- `AURA_WAKE_PAUSE_THRESHOLD`: pause duration used by recognition.
- `AURA_WAKE_AMBIENT_SEC`: ambient-noise calibration duration.
- `AURA_WAKE_TIMEOUT_SEC`: wait time for speech to begin.
- `AURA_WAKE_PHRASE_LIMIT_SEC`: maximum wake-phrase capture duration.
- `AURA_WAKE_DYNAMIC_ENERGY`: dynamic energy-threshold toggle.

## Project utility commands

```powershell
python project_tools.py list-mics
python project_tools.py calibrate-mics
python project_tools.py test-mic --index 1
python project_tools.py generate-token
python project_tools.py init-db
```

`generate-token` configures Gmail and Contacts OAuth scopes. `init-db` is a
legacy MySQL utility and expects a `SQL.sql` file; that file is not present in
the current project tree. The active authentication and history code use
SQLite.

## Data and privacy

- Account records and command history are stored in the local SQLite database.
- Assistant preferences and memory are stored in JSON files under `data/`.
- The app can send recognized speech or prompts to online services when those
  features are used.
- Review microphone, AI, email, OAuth, and packaging configuration before use
  or distribution. Do not share real credentials or user data.

## Learning outcomes and future work

This project brings together Python desktop UI development, voice processing,
natural-language command routing, desktop automation, API integration, SQLite,
local data management, and Windows packaging.

Potential areas for future improvement include more reliable offline speech
recognition, broader multilingual support, stronger contextual understanding,
expanded tests and error handling, and tighter permission controls for system
operations.

---

**Project:** Aura - Personal Desktop Voice Assistant
**Category:** Python desktop application
**Interface:** PyQt6
**Platform focus:** Windows
**Voice input:** SpeechRecognition
**Text-to-speech:** pyttsx3
**Local database:** SQLite
