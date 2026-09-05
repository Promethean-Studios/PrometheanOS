# PrometheanOS Repository Layout

## Top level

- `README.md` — user-facing overview and project status.
- `LICENSE` — MIT license.
- `docs/` — architecture, plans, and operational documentation.
- `src/` — product implementation source.
- `config/` — Fedora, KDE, systemd, and security configuration templates.
- `scripts/` — setup, install, validation, and repair automation.
- `build/` — generated artifacts and reproducible ISO build workspaces.
- `ai/` — AI runtime manifests, model metadata, and hardware recommendation data.

## Source modules

### `src/desktop/`

Responsibilities:

- Promethean KDE theming and custom styling.
- Dock, system tray, and panel behavior.
- Theme toggles for dark/light modes and low-end mode.
- Window controls and visual polish.

### `src/system/`

Responsibilities:

- Hardware inventory and diagnostics.
- CPU, GPU, memory, storage, and network data collection.
- Performance profile logic.
- Security policy, permission gates, and sandbox guidance.
- Recovery and rollback helpers.

### `src/ai/`

Responsibilities:

- AI runtime detection and setup.
- Model manifest and registry integration.
- Benchmark execution and performance comparison.
- Hardware-aware optimization recommendations.
- Local assistant permission logic and task runner scaffolding.

### `src/installer/`

Responsibilities:

- Kickstart and image generation workflows.
- Fedora install customization.
- QEMU validation and boot-testing scripts.
- Safe install guidance and recovery documentation.

### `src/lib/`

Responsibilities:

- Shared Python libraries.
- Metrics and hardware parsing helpers.
- Common logging, config handling, and validation utilities.
- Cross-subsystem shared data models.

## Configuration and runtime assets

### `config/`

The configuration layer is intentionally simple and native:

- KDE Plasma settings templates.
- systemd unit files for monitors and AI services.
- NetworkManager and PipeWire defaults.
- Security baselines and safe system policies.
- Performance profile definitions.

### `scripts/`

Scripts are the operational glue of the project:

- `scripts/setup/` — environment bootstrap and package installation.
- `scripts/validate/` — smoke tests for system detection, AI environment, and build flows.
- `scripts/recovery/` — repair and rollback helpers.
- `scripts/build/` — ISO and image generation automation.

### `build/`

This directory contains generated items only:

- kickstart artifacts,
- installer staging directories,
- QEMU images,
- test logs,
- package/manifest outputs.

### `ai/`

This directory keeps the AI side manageable and explicit:

- model catalog metadata,
- recommended runtime recipes,
- quantization guidance,
- app-level workflow manifests,
- benchmark definitions.

## Design principles for this layout

- Small modules with clear ownership.
- Native Fedora/KDE integration instead of custom platform layers.
- Real tooling first; no UI-only scaffolding.
- Testable automation for every major subsystem.
- Safe defaults and explicit permissions for any system-affecting task.

## Why this layout works well in Codespaces

A browser-based development environment is ideal for building the control plane, validation scripts, configuration templates, and AI automation logic before moving to a full Fedora install or QEMU image. This structure keeps the repository modular and testable without requiring a full OS build at every step.
