"""Optional tools, authentication and protocol checks; no scans or model calls."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import queue
import shutil
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from sources import read_json, safe_path, save_json
from setup_support import save_strix_settings, set_credential, strix_settings
from tool_runtime import (RECIPES, docker_status, install_runtime, runtime_status,
                          start_strix_login, strix_auth_status, probe_command)


def verify_mcps(root: Path) -> dict:
    from manage import Toolkit
    from probe import probe_mcps
    toolkit = Toolkit(root)
    # Only the two reviewed bundled MCP recipes are automated here.
    expected = {'context7': {'transport': 'http', 'url': 'https://mcp.context7.com/mcp', 'credential_env': 'CONTEXT7_API_KEY'},
                'testsprite': {'transport': 'stdio', 'package': '@testsprite/testsprite-mcp',
                              'credential_env': 'TESTSPRITE_API_KEY', 'server_env': 'API_KEY'}}
    selected = []
    skipped = {}
    for tool in toolkit.tools:
        if tool['id'] not in expected:
            continue
        declaration = dict(tool.get('mcp', {}))
        declaration.pop('version', None)  # Pinned package updates do not alter publisher/credential identity.
        if declaration != expected[tool['id']]:
            skipped[tool['id']] = {'status': 'custom-config-not-probed'}
        else:
            selected.append(tool)
    results = probe_mcps(root, selected, toolkit.state)
    results.update(skipped)
    save_json(safe_path(root, '.agent-toolkit/mcp-probes.json'),
              {'checked_at': datetime.now(timezone.utc).isoformat(), 'results': results})
    toolkit.inventory()
    return results


class ToolsWizard:
    def __init__(self, parent, project: Path):
        self.project = project.resolve()
        if not read_json(safe_path(self.project, '.agent-toolkit/project.json'), {}).get('provider'):
            raise ValueError('Install the toolkit and select a provider first')
        self.window = tk.Toplevel(parent)
        self.window.title('Agent Toolkit — guided tool setup')
        self.window.geometry('820x650')
        self.window.minsize(730, 590)
        self.events = queue.Queue()
        self.running = False
        self.login_child = None
        self.cancel = threading.Event()
        self.actions = []
        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Complete your tool setup', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Base agents and skills are installed. Select optional components below.\nSetup never runs application tests, pentests, model calls or repository uploads.').pack(anchor='w', pady=8)
        notebook = ttk.Notebook(frame)
        notebook.pack(fill='both', expand=True)
        tools = self.page(notebook, '1. Tools')
        auth = self.page(notebook, '2. Strix access')
        mcps = self.page(notebook, '3. MCP access & checks')
        self.selected = {}
        registered = {t['id'] for t in read_json(safe_path(self.project, '.agent-toolkit/registry.json'), {})['tools']}
        ttk.Label(tools, text='Install isolated runtimes inside this project. Existing global tools are preserved.\nSelect only tools you need; downloads may take several minutes.').pack(anchor='w', pady=(0, 8))
        for name, recipe in RECIPES.items():
            if name not in registered:
                continue
            variable = tk.BooleanVar(value=False)
            self.selected[name] = variable
            ttk.Checkbutton(tools, text=recipe.get('label', name), variable=variable).pack(anchor='w')
        self.action(tools, 'Install selected runtimes', self.install_selected)
        self.action(tools, 'Check installed CLI version/help', lambda: self.work(
            lambda: {name: probe_command(self.project, name) for name in self.selected}))
        ttk.Label(tools, text='Unknown/additional tools use their official documentation; no arbitrary installer\ncommands are taken from the registry. Docker remains a manual system prerequisite.').pack(anchor='w', pady=8)
        self.action(tools, 'Check Docker CLI and daemon', lambda: self.work(lambda: {'Docker': docker_status()}))
        ttk.Button(tools, text='Open official Docker installation guide', command=lambda: webbrowser.open('https://docs.docker.com/get-started/get-docker/')).pack(anchor='w', pady=4)
        ttk.Label(tools, text='Check the current OS requirements before installing Docker Desktop.\nOn unsupported Windows editions/builds, update Windows or use a supported host.').pack(anchor='w')
        settings = strix_settings(self.project)
        self.mode = tk.StringVar(value=settings['auth_mode'])
        self.model = tk.StringVar(value=settings['model'] or 'chatgpt/gpt-6.1-sol')
        ttk.Label(auth, text='Strix authentication is separate from your coding client.\nChatGPT sign-in is provided by Strix; actual model availability needs a separate check.').pack(anchor='w', pady=8)
        for label, value in [('Configure later', 'later'), ('Sign in with ChatGPT', 'chatgpt'), ('Use an API provider', 'api')]:
            ttk.Radiobutton(auth, text=label, variable=self.mode, value=value, command=self.change_mode).pack(anchor='w')
        ttk.Label(auth, text='Strix provider/model ID').pack(anchor='w', pady=(8, 0))
        ttk.Entry(auth, textvariable=self.model).pack(fill='x')
        self.action(auth, 'Save authentication choice', self.save_preferences)
        self.action(auth, 'Start ChatGPT browser sign-in', self.login)
        ttk.Button(auth, text='Cancel sign-in', command=self.cancel_login).pack(anchor='w', pady=4)
        self.action(auth, 'Check Strix authentication', lambda: self.work(lambda: {'Strix auth': strix_auth_status(self.project)}))
        ttk.Label(auth, text='Install the Strix runtime in step 1 before signing in. API mode uses LLM_API_KEY\nin step 3. Strix keeps its own login session; the toolkit never reads its token files.').pack(anchor='w', pady=8)
        self.credentials = {}
        ttk.Label(mcps, text='Keys are masked and never written to project files or logs.\nBlank entries keep the existing environment. Session-only is the default.').pack(anchor='w', pady=8)
        for name in ['CONTEXT7_API_KEY', 'TESTSPRITE_API_KEY', 'LLM_API_KEY']:
            label = name + (' — already present' if os.environ.get(name) else ' — missing')
            ttk.Label(mcps, text=label).pack(anchor='w')
            variable = tk.StringVar()
            self.credentials[name] = variable
            ttk.Entry(mcps, textvariable=variable, show='•').pack(fill='x', pady=(0, 4))
        self.persist = tk.BooleanVar(value=False)
        ttk.Checkbutton(mcps, text='Save entered keys to my Windows user environment (optional)', variable=self.persist).pack(anchor='w', pady=4)
        ttk.Label(mcps, text='This stores plaintext outside the project, accessible to your user and future processes.\nExisting different user values are preserved. Restart the client after saving.\nWithout this option, keys apply only to this setup session; configure future clients separately.').pack(anchor='w')
        self.action(mcps, 'Apply entered credentials', self.apply_credentials)
        self.action(mcps, 'Verify managed MCP connections', lambda: self.work(lambda: verify_mcps(self.project)))
        ttk.Label(mcps, text='Checks initialize Context7/TestSprite and list tools only. Custom MCPs are skipped.\nApprove servers and reload your AI client separately; a probe does not load this chat.').pack(anchor='w', pady=8)
        self.status = tk.StringVar(value='Choose tools or check existing setup')
        ttk.Label(frame, textvariable=self.status).pack(anchor='w', pady=(10, 0))
        self.output = tk.Text(frame, height=6, state='disabled', wrap='word', font=('Consolas', 9))
        self.output.pack(fill='x', pady=6)
        self.action(frame, 'Refresh setup summary', self.summary)
        ttk.Button(frame, text='Close', command=self.close).pack(anchor='e')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.after(100, self.poll)
        self.summary()

    def page(self, notebook, label):
        page = ttk.Frame(notebook, padding=12)
        notebook.add(page, text=label)
        return page

    def action(self, frame, label, command):
        button = ttk.Button(frame, text=label, command=command)
        button.pack(anchor='w', pady=4)
        self.actions.append(button)

    def append(self, text):
        self.output.configure(state='normal')
        self.output.insert('end', text + '\n')
        self.output.see('end')
        self.output.configure(state='disabled')

    def work(self, callback):
        if self.running:
            return
        self.running = True
        self.cancel.clear()
        self.status.set('Working…')
        for button in self.actions:
            button.configure(state='disabled')
        def worker():
            try:
                self.events.put(('done', callback()))
            except Exception as error:
                self.events.put(('error', type(error).__name__))
        threading.Thread(target=worker, daemon=True).start()

    def install_selected(self):
        names = [name for name, variable in self.selected.items() if variable.get()]
        if not names:
            self.status.set('Select at least one runtime')
            return
        def install():
            results = {}
            for name in names:
                try:
                    results[name] = install_runtime(self.project, name, log=lambda line: self.events.put(('log', line)))
                except Exception as error:
                    results[name] = {'status': 'failed', 'detail': type(error).__name__}
            return results
        self.work(install)

    def save_preferences(self):
        try:
            save_strix_settings(self.project, self.mode.get(), self.model.get())
            self.status.set('Authentication choice saved; model execution remains unverified')
        except ValueError as error:
            messagebox.showerror('Check Strix preferences', str(error), parent=self.window)

    def change_mode(self):
        if self.mode.get() == 'chatgpt' and not self.model.get().startswith('chatgpt/'):
            self.model.set('chatgpt/gpt-6.1-sol')
        elif self.mode.get() == 'api' and self.model.get().startswith('chatgpt/'):
            self.model.set('')

    def login(self):
        if self.mode.get() != 'chatgpt':
            self.status.set('Choose ChatGPT authentication first')
            return
        try:
            save_strix_settings(self.project, self.mode.get(), self.model.get())
        except ValueError as error:
            messagebox.showerror('Check Strix preferences', str(error), parent=self.window)
            return
        def authenticate():
            child = start_strix_login(self.project)
            self.login_child = child
            try:
                deadline = time.monotonic() + 300
                while child.poll() is None and time.monotonic() < deadline and not self.cancel.is_set():
                    time.sleep(0.2)
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except Exception:
                        child.kill(); child.wait(timeout=5)
                    return {'Strix auth': {'status': 'cancelled' if self.cancel.is_set() else 'timed-out'}}
                return {'Strix auth': strix_auth_status(self.project)}
            finally:
                self.login_child = None
        self.work(authenticate)

    def cancel_login(self):
        self.cancel.set()

    def apply_credentials(self):
        entries = [(name, value.get()) for name, value in self.credentials.items() if value.get()]
        persist = self.persist.get()
        # Remove secrets from the GUI immediately; the worker reports names/statuses only.
        for value in self.credentials.values():
            value.set('')
        def apply():
            results = {}
            for name, value in entries:
                try:
                    results[name] = {'status': set_credential(name, value, persist=persist)}
                except Exception as error:
                    results[name] = {'status': 'not-saved', 'detail': type(error).__name__,
                                     'message': 'Check the entry and existing user environment; differing values are preserved.'}
            return results
        self.work(apply)

    def summary(self):
        def collect():
            report = {name: runtime_status(self.project, name) for name in self.selected}
            report['Docker'] = {'status': 'command-detected; daemon-not-checked' if shutil.which('docker') else 'missing',
                                'message': 'Use Check Docker CLI and daemon for a readiness check.'}
            report['Strix auth'] = strix_auth_status(self.project)
            return report
        self.work(collect)

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == 'log':
                self.append(value)
                continue
            self.running = False
            for button in self.actions:
                button.configure(state='normal')
            if kind == 'error':
                self.append('Optional setup failed: ' + value + '. Base toolkit remains installed.')
                self.status.set('Optional setup needs attention')
            else:
                for name, result in value.items():
                    self.append(name + ': ' + str(result.get('status', 'unknown')) +
                                ('; ' + str(result['version']) if result.get('version') else '') +
                                ('; ' + str(result['message']) if result.get('message') else ''))
                self.status.set('Checks completed; review each result and reload the client when ready')
        if self.window.winfo_exists():
            self.window.after(100, self.poll)

    def close(self):
        if self.running:
            messagebox.showinfo('Setup in progress', 'Wait for the current operation, or cancel sign-in first.', parent=self.window)
        else:
            self.window.destroy()


def open_setup(project: Path) -> None:
    root = tk.Tk()
    root.withdraw()
    wizard = ToolsWizard(root, project)
    wizard.window.bind('<Destroy>', lambda event: root.destroy() if event.widget == wizard.window else None)
    root.mainloop()
