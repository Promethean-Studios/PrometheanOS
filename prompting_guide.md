You are the lead engineer building **PrometheanOS V1**, an AI-first Linux desktop environment based on **Fedora KDE Plasma**. Build a functional, installable, polished V1—not a mockup or concept. Make reasonable engineering decisions without repeatedly asking for approval.

## CORE PRINCIPLE

PrometheanOS should feel like an OS designed for local AI from the ground up while remaining a normal, stable Linux desktop. Do NOT write a custom kernel, filesystem, package manager, or GPU driver. Build on Fedora/KDE and focus engineering effort on the AI experience, hardware optimization, UX, and tooling.

## 1. FOUNDATION

* Fedora KDE Plasma base
* x86_64/UEFI
* Wayland by default
* systemd, NetworkManager, PipeWire
* DNF/RPM + Flatpak
* Podman/container support
* automatic updates
* rollback/recovery strategy
* normal Linux applications and terminal must continue working
* produce reproducible build/install scripts and an installable ISO when practical

## 2. PROMETHEAN UI

Create an original, polished **macOS-inspired** interface without copying Apple's proprietary assets.

* Promethean branding
* custom wallpaper, icons, cursor, typography and system styling
* clean dock
* elegant top bar/system tray
* rounded windows, blur/transparency where performance allows
* smooth but restrained animations
* dark/light modes
* consistent spacing and visual language
* low-end mode that automatically reduces expensive effects

Visual references:

* https://ibb.co/MxxYn9qw
* https://ibb.co/fzdKg7Nj
* https://ibb.co/bZKr6g8
* https://ibb.co/PLcMn07

Use these as design inspiration, not assets to copy.

## 3. PROMETHEAN CONTROL CENTER

Build a flagship system/AI dashboard showing:

* CPU usage, temperature, frequency
* RAM usage
* GPU usage, temperature, clock, power
* VRAM usage
* storage usage/activity
* network activity
* active AI workloads
* model memory usage
* inference tokens/sec and latency when available

Include controls for performance profiles and safe resource limits.

## 4. AI-FIRST RUNTIME

Make local AI setup dramatically easier.
Support/detect/manage where hardware permits:

* NVIDIA drivers
* CUDA + CUDA Toolkit
* cuDNN
* PyTorch
* Python/venv
* Hugging Face Transformers + Hub
* llama.cpp
* Ollama
* Jupyter
* ONNX Runtime
* vLLM
* TensorRT/TensorRT-LLM
* bitsandbytes
* Unsloth
* ROCm where applicable

Create an AI setup/diagnostic system that detects broken configurations and clearly explains/fixes common issues.

## 5. MODEL MANAGER

Create an AI model management application:

* search supported model registries, especially Hugging Face
* model metadata
* parameters
* quantization
* context length
* size/download size
* estimated RAM/VRAM requirements
* hardware compatibility
* one-click download/install where practical
* launch/configure/delete models
* manage model/cache storage
* detect duplicate/unused models

## 6. HARDWARE-AWARE OPTIMIZATION

Analyze the user's machine and recommend realistic AI configurations.
Automatically estimate:

* suitable model sizes
* quantization
* CPU/GPU offloading
* context limits
* batch sizes
* thread counts
* memory requirements

Provide:

* Balanced Mode
* AI Performance Mode
* Low-End Mode
* Developer Mode

Never silently make dangerous system changes.

## 7. LOCAL AI ASSISTANT

Create an optional local assistant capable of:

* explaining system status
* diagnosing hardware/software issues
* helping configure AI environments
* assisting with local AI workflows

Use explicit permissions. Never give an AI unrestricted root access.

Permissions should distinguish:

* read system information
* install software
* modify configuration
* execute commands
* delete files
* root/administrator actions

Dangerous actions require confirmation.

## 8. AI BENCHMARK CENTER

Create benchmarking for:

* CPU
* RAM
* GPU
* VRAM
* storage
* local model inference

Show:

* tokens/sec
* latency
* prompt processing speed
* VRAM/RAM usage
* temperature/power where available

## 9. DEVELOPER ENVIRONMENT

Provide easy setup for:

* Git
* GitHub CLI
* Python
* C/C++
* Rust
* Node.js
* containers/Podman
* Jupyter
* CUDA development
* SSH
* common build tools

Include an easy AI-project initialization workflow.

## 10. RESOURCE + STORAGE MANAGEMENT

Create AI-aware resource/storage management:

* identify AI processes
* monitor resource consumption
* safely pause/limit workloads
* model/cache/dataset storage breakdown
* duplicate/unused model detection
* safe cleanup tools

## 11. SECURITY + PRIVACY

Treat security as a core feature.

* sandbox AI workloads where appropriate
* least-privilege design
* no unrestricted AI root access
* safe command execution
* resource limits
* network restrictions where appropriate
* secure defaults
* clear permission prompts
* never transmit user data without explicit user action

## 12. RECOVERY

Provide:

* system snapshots/rollback where practical
* recovery mode
* package repair
* configuration recovery
* driver troubleshooting
* boot-repair documentation
* safe fallback if an AI-generated change breaks something

## 13. EXTENSIBLE ARCHITECTURE

Design PrometheanOS so future AI frameworks, hardware vendors, model registries and applications can integrate through clean APIs/plugins without rewriting the OS.

Do NOT implement Talos, TalosCloud, distributed compute, or other Promethean projects yet. Keep the architecture extensible for future integration, but leave them completely out of V1.

## 14. INSTALLATION + BUILD

Create a reproducible development/build workflow and work toward an actual bootable ISO. Test primarily in QEMU/VMs before recommending physical installation.

Never overwrite physical disks or modify boot configuration without explicit user confirmation.

## ENGINEERING RULES

* Inspect the existing repository before making architectural decisions.
* Build real functionality, not placeholder UI.
* Prefer stable Fedora/KDE/Linux APIs over hacks.
* Keep components modular and maintainable.
* Avoid unnecessary dependencies.
* Test every major component.
* Document setup, build, testing and recovery.
* Handle missing hardware gracefully.
* NVIDIA hardware should receive first-class CUDA optimization, but the OS must remain functional without NVIDIA hardware.
* Keep the UI polished and performant.
* Do not claim a feature works unless it has been tested.
* Commit changes logically and keep the repository clean.

## DEFINITION OF DONE

A successful V1 should boot into a distinctly **Promethean** desktop, provide a polished Control Center, detect and report hardware, provide an AI environment setup workflow, manage local models, provide hardware-aware AI optimization, include developer tooling, recovery/security systems, and have a reproducible path to an installable ISO.

Start by inspecting the repository and environment, then create a concise implementation plan. After planning, **build the working V1 incrementally and test each subsystem rather than stopping at documentation or mockups.**
