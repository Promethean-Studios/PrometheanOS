# PrometheanOS

PrometheanOS is a Fedora-based Linux desktop environment designed for local AI workloads. It builds on Fedora KDE Plasma and adds hardware-aware diagnostics, model management, local inference services, and a Promethean Control Center.

## Architecture overview

The system is organized into modular layers:

- Fedora Workstation base
  - Fedora KDE Plasma live environment with systemd, NetworkManager, PipeWire, and SDDM
  - DNF/RPM package management, Firewalld, NetworkManager, PipeWire
  - Podman support for containerized AI services

- Promethean desktop and user experience
  - custom shell and branding
  - performance profiles and hardware-aware optimization
  - local control center and status views

- AI runtime and model layer
  - hardware-aware CUDA/ROCm availability detection
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

Optional GPU container services are isolated behind the `gpu` Compose profile;
the desktop, API, hardware detection, and model inventory do not require a GPU.

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

1. Ensure Podman is installed and configured for privileged containers.
2. Ensure the host has enough disk space for Fedora packages and a live ISO.
3. From the repo root:

```bash
chmod +x build.sh
./build.sh
```

The builder uses `kickstarts/promethean-live.ks` and writes the ISO to
`build/output/`. It does not write to host disks. Fedora release and output can
be overridden, for example:

```bash
FEDORA_RELEASE=44 OUTPUT_DIR="$PWD/build/output" ./build.sh
```

### Kickstart customization

The main installation definition is:

- `kickstarts/promethean-live.ks`

It configures:

- Fedora KDE Plasma live environment
- default non-root user with sudo access
- KDE Plasma desktop and system services
- Python backend and Promethean Control Center
- default local AI cache locations

## Cloud ISO Build

To build the ISO on an Ubuntu GitHub-hosted runner, open the repository's
**Actions** tab, select **Build PrometheanOS ISO**, choose **Run workflow**, and
start the workflow. When it completes, open the workflow run and download the
`PrometheanOS-KDE-ISO` artifact. It contains
`build/output/PrometheanOS-KDE.iso`.

## Testing with QEMU / KVM

Use QEMU/KVM to validate the live image before approaching physical hardware.

### Example QEMU command

```bash
./scripts/qemu-smoke-test.sh ./build/output/PrometheanOS-KDE.iso
```

The repository's smoke test is the reproducible validation path for the live ISO. It uses a UEFI-enabled x86_64 VM and intentionally does not write to host disks.

For an interactive desktop test, omit `-display none` in the script or run:

```bash
qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu max \
  -m 4096 \
  -smp 2 \
  -bios /usr/share/edk2/ovmf/OVMF_CODE.fd \
  -cdrom ./build/output/PrometheanOS-KDE.iso \
  -vga virtio \
  -nic user,model=virtio \
  -display gtk
```

### Alpha 0.1 validation milestone

This repository aims to support a first bootable Fedora KDE live image for QEMU testing. The expected flow is:

1. build the ISO with `./build.sh`
2. confirm `build/output/PrometheanOS-KDE.iso` exists
3. run `./scripts/qemu-smoke-test.sh ./build/output/PrometheanOS-KDE.iso`
4. verify the live environment reaches the Fedora KDE desktop and systemd is healthy
5. check Promethean services and telemetry endpoints from the running system

Known limitations for the current Alpha 0.1 milestone:

- this is a Fedora KDE live image, not a full installed OS deployment yet
- GPU/CUDA runtime is optional and should degrade gracefully on CPU-only or VM hardware
- QEMU tests are smoke-level validation, not a full hardware certification pass
- local AI features are gated by runtime availability and are not expected to be fully operational without a model or GPU

### KVM recommendations

- allocate at least 4–8 GB RAM for a realistic workstation test
- give the VM 4 CPU cores for local model testing
- use virtio disks and `-enable-kvm` when the host supports it
- keep networking on a user-mode bridge for simple testing

## Validation and CI

The repository includes GitHub Actions workflows for validation:

- `.github/workflows/lint.yml` runs shellcheck on shell scripts and ruff on Python files
- `.github/workflows/kickstart-validate.yml` runs `ksvalidator` against Kickstart files

Run the local backend tests with:

```bash
python3 -m pytest -q
```

## Security and operational expectations

- Local AI services are constrained to localhost by default whenever possible
- destructive actions require confirmation and privileged intent
- GPU runtime setup is explicit and hardware-aware
- logs are kept in standard system locations such as `/var/log/promethean-hardware.log`

## Future directions

PrometheanOS V1 focuses on a clean, stable Fedora base with AI-first workflows layered on top, while leaving future extensibility for additional model registries, dashboards, and hardware integrations without rewriting the OS.
