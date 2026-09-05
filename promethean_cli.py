#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:  # pragma: no cover - fallback for minimal systems
    class Console:
        def print(self, *args, **kwargs):
            print(*args)

    class Panel:
        @staticmethod
        def fit(title, style=None):
            return title

    class Table:
        def __init__(self, *args, **kwargs):
            self.rows = []

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            self.rows.append(args)

        def __str__(self):
            return " | ".join(str(item) for item in self.rows[-1]) if self.rows else ""

    Console = Console
    Panel = Panel
    Table = Table

console = Console()


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", "command not found"


def print_header(title):
    console.print(Panel.fit(title, style="bold cyan"))


def check_kernel():
    kernel = Path('/proc/version').read_text(encoding='utf-8', errors='ignore').strip()
    return {"Kernel": kernel.split()[2] if len(kernel.split()) >= 3 else kernel}


def check_gpu():
    gpu = "Unknown"
    if shutil.which('nvidia-smi'):
        code, out, _ = run_cmd(['nvidia-smi'])
        gpu = out.splitlines()[0] if out else 'NVIDIA GPU detected'
    elif shutil.which('lspci'):
        code, out, _ = run_cmd(['lspci'])
        if 'NVIDIA' in out or 'nvidia' in out:
            gpu = 'NVIDIA (lspci)'
        elif 'AMD' in out or 'Radeon' in out or 'AMD' in out:
            gpu = 'AMD'
        elif 'Intel' in out or 'intel' in out:
            gpu = 'Intel'
        else:
            gpu = 'No supported GPU detected'
    return {"GPU": gpu}


def check_driver_status():
    status = []
    for name, cmd in [
        ('NVIDIA driver', ['nvidia-smi']),
        ('CUDA', ['nvcc', '--version']),
        ('ROCm', ['rocminfo']),
        ('Podman', ['podman', '--version']),
        ('Docker', ['docker', '--version']),
    ]:
        code, out, err = run_cmd(cmd)
        status.append((name, 'OK' if code == 0 else 'MISSING'))
    return dict(status)


def check_runtime_status():
    runtimes = {}
    for runtime in ['podman', 'docker', 'nerdctl']:
        runtimes[runtime] = 'available' if shutil.which(runtime) else 'missing'
    return runtimes


def doctor_command():
    print_header('Promethean doctor')
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('Check')
    table.add_column('Status')

    kb = check_kernel()
    table.add_row('Kernel', kb.get('Kernel', 'Unknown'))

    gpu_data = check_gpu()
    table.add_row('GPU', gpu_data.get('GPU', 'Unknown'))

    for key, value in check_driver_status().items():
        table.add_row(key, value)

    for key, value in check_runtime_status().items():
        table.add_row(f'Container runtime: {key}', value)

    console.print(table)


def start_service(service_name):
    valid = {'ollama': 'promethean-ollama.service', 'vllm': 'promethean-vllm', 'webui': 'promethean-open-webui', 'comfyui': 'promethean-comfyui'}
    if service_name not in valid:
        console.print(f'[red]Unsupported service: {service_name}[/red]')
        return 1

    target = valid[service_name]
    if service_name == 'ollama':
        cmd = ['systemctl', 'enable', '--now', target]
    else:
        cmd = ['podman', 'compose', '-f', '/etc/promethean/compose.yaml', 'up', '-d', service_name]
    code, out, err = run_cmd(cmd)
    if code == 0:
        console.print(f'[green]Started {service_name} successfully.[/green]')
    else:
        console.print(f'[red]Failed to start {service_name}: {err or out}[/red]')
    return code


def list_models():
    print_header('Local model inventory')
    table = Table(show_header=True, header_style='bold green')
    table.add_column('Source')
    table.add_column('Path / Name')

    candidate_paths = [
        ('HuggingFace', '/data/models/huggingface'),
        ('Ollama', '/data/models/ollama'),
        ('Default cache', '/root/.cache/huggingface'),
        ('User cache', '/home/*/.cache/huggingface'),
    ]

    discovered = []
    for source, path in candidate_paths:
        path_obj = Path(path)
        if path_obj.exists():
            if path_obj.is_dir():
                entries = sorted(p.name for p in path_obj.iterdir() if p.is_dir() or p.is_file())
                if entries:
                    discovered.append((source, ', '.join(entries[:10])))
                else:
                    discovered.append((source, 'empty'))
            else:
                discovered.append((source, str(path_obj)))
        else:
            discovered.append((source, 'not found'))

    for source, name in discovered:
        table.add_row(source, name)

    console.print(table)
    return 0


def update_system():
    print_header('Promethean update')
    steps = [
        ['dnf', 'upgrade', '-y'],
        ['podman', 'image', 'prune', '-f'],
        ['ollama', 'pull', 'llama3.1'],
    ]

    for step in steps:
        step_text = ' '.join(step)
        console.print(f'[bold]Running:[/bold] {step_text}')
        code, out, err = run_cmd(step)
        if code != 0:
            console.print(f'[yellow]Step failed: {step_text}: {err or out}[/yellow]')
        else:
            console.print('[green]Step succeeded.[/green]')

    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog='promethean', description='PrometheanOS command line utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('doctor', help='run system diagnostics')

    start_parser = subparsers.add_parser('start', help='start a service or stack')
    start_parser.add_argument('service', choices=['ollama', 'vllm', 'webui', 'comfyui'])

    models_parser = subparsers.add_parser('models', help='model management')
    models_subparsers = models_parser.add_subparsers(dest='models_command', required=True)
    models_subparsers.add_parser('list', help='list locally downloaded models')

    subparsers.add_parser('update', help='update system AI tooling and container images')
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == 'doctor':
        return doctor_command()
    if args.command == 'start':
        return start_service(args.service)
    if args.command == 'models':
        return list_models()
    if args.command == 'update':
        return update_system()

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
