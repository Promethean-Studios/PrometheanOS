# PrometheanOS V1 Implementation Plan

## Mission

PrometheanOS V1 is a Fedora KDE Plasma desktop optimized for local AI workloads, with real hardware detection, a polished desktop UX, developer tooling, model management, and a reproducible install path. The project is not a custom kernel or a mockup; it is a Fedora-based, systemd-driven environment that layers Promethean-specific automation, UX, and AI workflows on top of the Fedora Linux platform.

## Repository layout

The repository is organized around a small number of responsibilities so the project can be built incrementally and tested in a browser-based Codespace before moving to QEMU or a real machine.

### Top-level structure

- `README.md` — project overview, status, and user-facing guidance.
- `docs/` — architecture, implementation plans, and operating procedures.
- `src/` — source code for the actual features and subsystems.
- `config/` — Fedora/KDE and system configuration templates.
- `scripts/` — build, setup, validation, and repair scripts.
- `build/` — generated artifacts, ISO work directories, and reproducible build outputs.
- `ai/` — model registry metadata, runtime recipes, and AI environment manifests.

### Source tree

- `src/desktop/` — Promethean shell/theme components, dock, system tray, and desktop policy scripts.
- `src/system/` — hardware detection, resource monitoring, permissions, security policies, and recovery logic.
- `src/ai/` — model manager, benchmark harness, runtime detection, hardware recommendations, and AI setup diagnostics.
- `src/installer/` — Kickstart, Anaconda, image build, and installation logic.
- `src/lib/` — shared Python libraries and common utilities used across the project.

## Execution plan

### Phase 1: Foundation and automation

- Define the mandatory Fedora KDE baseline and version constraints.
- Create a reproducible setup flow for Codespaces and local build environments.
- Define the package manifest for core Fedora and RPM packages: Plasma, Wayland, PipeWire, Podman, Python, Node, Rust, Git, GitHub CLI, and developer tooling.
- Add a validation script that checks installed prerequisites and hardware capability.

### Phase 2: Hardware and control center

- Build a hardware inventory module that reports CPU, GPU, memory, storage, and networking details.
- Add thermal and power telemetry collection for supported Linux backends.
- Implement the Promethean Control Center as a readable, real dashboard with safe limits and profile controls.
- Support low-end, balanced, performance, and developer modes without changing system state without confirmation.

### Phase 3: AI runtime and diagnostics

- Detect NVIDIA, ROCm, CPU-only, and containerized AI paths.
- Install and validate Python virtual environments, PyTorch, Transformers, llama.cpp, Ollama, vLLM, and common ML tooling.
- Add diagnostic checks for broken CUDA, missing drivers, invalid Python envs, and model cache issues.
- Provide a repair flow that explains root cause and safe recovery steps before making changes.

### Phase 4: Model management and benchmarking

- Build a model registry abstraction with Hugging Face and local cache support.
- Add model metadata analysis: quantization, context length, size, memory requirements, and viability checks.
- Build benchmark tooling for CPU, GPU, VRAM, storage, and local inference.
- Allow one-click install and launch actions where the underlying runtime supports them.

### Phase 5: Desktop polish and UX

- Implement Promethean theming and basic desktop shell customization for KDE Plasma.
- Add a dock, top bar, window polish, and accessibility modes.
- Support dark/light themes and a low-end performance mode that reduces expensive visual effects automatically.
- Keep the desktop operational and familiar for standard Linux use.

### Phase 6: Resource management, recovery, and security

- Implement per-workload resource constraints for AI tasks.
- Add safe cleanup, duplicate model detection, and model cache management.
- Add rollback and recovery paths using Fedora-native snapshots and documented recovery procedures.
- Enforce least-privilege AI permissions and confirmation for destructive actions.

### Phase 7: ISO and testability

- Build a reproducible image flow for Fedora Live/Kickstart installs.
- Validate the image in QEMU before recommending physical installation.
- Capture installation, recovery, and troubleshooting procedures in the docs.
- Ensure every major component is tested before calling it complete.

## Implementation rules

- Use Fedora/KDE native services instead of custom kernels or custom package managers.
- Prefer Python and shell tooling where they are stable and maintainable.
- Treat the browser-based environment as a development sandbox, not as the final target runtime.
- Every major subsystem must be tested with a real validation process.
- If a component cannot be verified in this environment, it must be documented as unverified rather than claimed as complete.

## First milestone

The first working milestone is a repository that contains:

1. a validated setup flow for Fedora/KDE and Codespaces,
2. a real hardware detection module,
3. a Promethean Control Center skeleton backed by live metrics,
4. an AI toolkit bootstrap and diagnostic workflow,
5. a documented build-to-QEMU validation path.

That milestone is the minimum credible V1 foundation.
