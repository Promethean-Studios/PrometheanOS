# PrometheanOS — Intended Architecture

This document describes the **intended** architecture of PrometheanOS. It is a
design sketch, not a description of an implemented system. No part of the
operating system described here has been built yet.

## Goals

PrometheanOS aims to be a small, well-documented operating system with an
emphasis on clarity over feature breadth. The goals are:

- **Minimalism** — A small kernel and a small userspace.
- **Clarity** — Code and design choices should be easy to follow.
- **Portability** — Architecture-specific code should be isolated.
- **Documentation** — Design decisions are recorded alongside the code.

## High-Level Structure

The intended system is organized into the following layers, from lowest to
highest privilege:

1. **Bootloader** — Loads the kernel into memory and transfers control to it.
   Intended to be a small, existing bootloader (e.g. a multiboot-compliant one)
   rather than something custom.
2. **Kernel** — The core of the OS. Provides memory management, process
   scheduling, interrupt handling, and basic device drivers.
3. **System Services** — Long-running userspace processes that expose OS
   functionality (file systems, networking, device management) to applications.
4. **Userspace** — Application programs that run on top of the system services.

## Kernel Subsystems (Planned)

- **Memory management** — Physical and virtual memory allocation, paging.
- **Process management** — Process and thread creation, scheduling, IPC.
- **Interrupt handling** — Hardware and software interrupt dispatch.
- **Device drivers** — Minimal drivers for essential devices (console, disk,
  timer).

## Userspace (Planned)

- A small standard library.
- A handful of core utilities.
- A simple shell.

## Non-Goals (For Now)

- A graphical desktop.
- Networking stack.
- POSIX compatibility.
- Multi-architecture support beyond the initial target.

## Status

This document is a placeholder. It will be updated as design decisions are made
and as the implementation progresses.
