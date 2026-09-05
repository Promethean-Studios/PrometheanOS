# PrometheanOS

PrometheanOS is a Fedora-based Linux desktop environment designed for local AI workloads. It intentionally builds on stable Fedora Workstation components and adds a curated AI-first operating model with hardware-aware configuration, model management, local inference services, and a polished control-center experience.

## Architecture overview

The system is organized into modular layers:

- Fedora Workstation base
  - Fedora 40/41 Workstation with standard GNOME/Wayland desktop defaults and systemd support
  - DNF/RPM package management, Firewalld, NetworkManager, PipeWire
  - Podman support for containerized AI services

- Promethean desktop and user experience
  - custom shell and branding
  - performance profiles and hardware-aware optimization
  - local control center and status views

- AI runtime and model layer
  - CUDA/ROCm detection and setup
  - Ollama for local model serving
  - vLLM for OpenAI-compatible local inference
  - Open WebUI and ComfyUI as optional services
  - Hugging Face cache and local model storage under /data/models

- System support layer
  - hardware detection and diagnostics
  - role-based permissions and explicit confirmation for dangerous operations
  - recovery, rollback, and repair guidance

## Hardware requirements

### NVIDIA

Recommended for the highest-performance local AI workloads.

- NVIDIA GPU with supported driver stack
- CUDA toolkit and NVIDIA proprietary drivers
- Fedora NVIDIA repo and/or negativo17 repo configuration
- PCIe GPU with adequate VRAM for target model sizes
- Suitable for local inference and training workloads when supported by software

Minimum recommended checks:

- `nvidia-smi` available
- `nvcc --version` available
- loaded NVIDIA kernel module
- CUDA-friendly container runtime configuration

### AMD

Suitable for ROCm-enabled AI tasks.

- AMD GPU with ROCm-compatible supported family
- access to `/dev/kfd` and `/dev/dri`
- ROCm runtime packages installed and configured
- `HSA_OVERRIDE_GFX_VERSION` can be set for standard RDNA2/3 cards

Recommended checks:

- `rocminfo` available
- GPU device nodes and permissions valid
- `rocm` runtime packages installed

### Intel

Intel GPUs can provide local media and some compute capabilities, but they are not the primary focus for the highest-end local AI workloads.

### CPU-only systems

PrometheanOS remains usable on CPU-only systems, but AI latency and throughput will be lower. The system should degrade gracefully and warn when heavier model workloads exceed the machine's practical limits.

## Repository layout

- `kickstarts/` — Fedora Kickstart files
- `systemd/` — systemd service files
- `scripts/` — operational helper scripts
- `etc/promethean/compose.yaml` — optional local AI stack via Podman Compose
- `docs/` — implementation and architecture documentation
- `.github/workflows/` — CI validation and linting
- `build.sh` — local ISO creation helper
- `setup-dev-env.sh` — Python toolchain/bootstrap setup for uv, pixi, and model cache directories

## Local build workflow

### Build the ISO locally

The repository includes a build script for a live ISO image using Podman and Fedora tooling.

1. Ensure Podman is installed.
2. Ensure you have a Fedora host (or a Fedora-based container environment) with enough disk space.
3. From the repo root:

```bash
chmod +x build.sh
./build.sh
```

This will build a live image using the Kickstart file in `kickstarts/promethean-base.ks` and write the output to the build directory.

### Kickstart customization

The main installation definition is:

- `kickstarts/promethean-base.ks`

It configures:

- base Fedora Workstation install
- default non-root user with sudo access
- RPM Fusion repositories
- NVIDIA/CUDA repo settings
- build tools and Python development packages
- default local AI cache locations

## Testing with QEMU / KVM

Use QEMU/KVM to validate the installation image before approaching physical hardware.

### Example QEMU command

```bash
qemu-system-x86_64 \
  -m 8G \
  -smp 4 \
  -drive file=./build/output/PrometheanOS-live.iso,format=raw,if=virtio \
  -vga virtio \
  -display gtk \
  -netdev user,id=n1 -device virtio-net-pci,netdev=n1 \
  -enable-kvm
```

### KVM recommendations

- allocate at least 4–8 GB RAM for a realistic workstation test
- give the VM 4 CPU cores for local model testing
- use virtio disks and `-enable-kvm` when the host supports it
- keep networking on a user-mode bridge for simple testing

## Validation and CI

The repository includes GitHub Actions workflows for validation:

- `.github/workflows/lint.yml` runs shellcheck on shell scripts and ruff on Python files
- `.github/workflows/kickstart-validate.yml` runs `ksvalidator` against Kickstart files

## Security and operational expectations

- Local AI services are constrained to localhost by default whenever possible
- destructive actions require confirmation and privileged intent
- GPU runtime setup is explicit and hardware-aware
- logs are kept in standard system locations such as `/var/log/promethean-hardware.log`

## Future directions

PrometheanOS V1 focuses on a clean, stable Fedora base with AI-first workflows layered on top, while leaving future extensibility for additional model registries, dashboards, and hardware integrations without rewriting the OS.
