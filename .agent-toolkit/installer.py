"""English setup wizard; can also install non-interactively and verify the packaged UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from installer_core import PROVIDERS, Project, install_from_repository
from setup_wizard import ToolsWizard, open_setup


class Wizard:
    def __init__(self, root):
        self.root = root
        self.root.title("Agent Toolkit Setup")
        self.root.geometry("780x610")
        self.root.minsize(650, 500)
        self.events = queue.Queue()
        self.running = False
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Set up your project agents", font=("Segoe UI", 19, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="Install agents, skills and MCP configuration from the latest stable release.").grid(row=1, column=0, columnspan=3, sticky="w", pady=(8,20))
        self.name = tk.StringVar()
        self.destination = tk.StringVar()
        self.provider = tk.StringVar(value="")
        self.strong = tk.StringVar(value="openai/gpt-6.1-sol")
        self.light = tk.StringVar(value="openai/gpt-6-luna")
        self.escalation = tk.StringVar(value="openai/gpt-6-astra")
        self.fields = []
        for row, label, variable in [(2,"Project name",self.name),(3,"Project folder",self.destination)]:
            ttk.Label(frame,text=label).grid(row=row,column=0,sticky="w",padx=(0,12),pady=5)
            entry=ttk.Entry(frame,textvariable=variable)
            entry.grid(row=row,column=1,columnspan=1 if row==3 else 2,sticky="ew",pady=5)
            self.fields.append(entry)
        self.browse=ttk.Button(frame,text="Browse...",command=self.choose_folder)
        self.browse.grid(row=3,column=2,padx=(8,0))
        ttk.Label(frame,text="Provider / environment").grid(row=4,column=0,sticky="w",pady=5)
        self.select=ttk.Combobox(frame,textvariable=self.provider,values=list(PROVIDERS),state="readonly")
        self.select.grid(row=4,column=1,columnspan=2,sticky="ew",pady=5)
        self.select.bind("<<ComboboxSelected>>",self.change_provider)
        self.models=ttk.LabelFrame(frame,text="OpenCode model IDs (provider/model-id)",padding=8)
        self.models.grid(row=5,column=0,columnspan=3,sticky="ew",pady=8)
        self.models.columnconfigure(1,weight=1)
        for row,label,variable in [(0,"Main agents",self.strong),(1,"Light agents",self.light),(2,"Escalation",self.escalation)]:
            ttk.Label(self.models,text=label).grid(row=row,column=0,sticky="w",padx=(0,12))
            entry=ttk.Entry(self.models,textvariable=variable)
            entry.grid(row=row,column=1,sticky="ew",pady=2)
            self.fields.append(entry)
        self.change_provider()
        ttk.Label(frame,text="Requires Git, Python 3.11+, Node.js/npm. No GitHub sign-in needed.\nAPI keys stay in environment variables. Optional audit CLIs are reported separately.",wraplength=680).grid(row=6,column=0,columnspan=3,sticky="w",pady=8)
        self.guide=tk.BooleanVar(value=True)
        ttk.Checkbutton(frame,text="Guide optional tool setup after installation",variable=self.guide).grid(row=7,column=0,columnspan=2,sticky="w")
        self.configure=ttk.Button(frame,text="Configure existing tools",command=self.configure_tools)
        self.configure.grid(row=7,column=2,sticky="e")
        self.button=ttk.Button(frame,text="Install toolkit",command=self.start)
        self.button.grid(row=8,column=2,sticky="e",pady=8)
        self.status=tk.StringVar(value="Ready")
        ttk.Label(frame,textvariable=self.status).grid(row=9,column=0,columnspan=3,sticky="w")
        self.log=tk.Text(frame,height=8,wrap="word",state="disabled",font=("Consolas",9))
        self.log.grid(row=10,column=0,columnspan=3,sticky="nsew",pady=(8,0))
        frame.rowconfigure(10,weight=1)
        self.root.protocol("WM_DELETE_WINDOW",self.close)
        self.root.after(100,self.poll)

    def choose_folder(self):
        selected=filedialog.askdirectory(title="Choose the project folder")
        if selected:
            self.destination.set(selected)
            if not self.name.get():
                self.name.set(Path(selected).name)

    def change_provider(self,event=None):
        if PROVIDERS.get(self.provider.get())=="opencode": self.models.grid()
        else: self.models.grid_remove()

    def configure_tools(self):
        try:
            if not self.destination.get().strip():
                raise ValueError("Choose the installed project folder first.")
            ToolsWizard(self.root,Path(self.destination.get()))
        except (ValueError,OSError,KeyError):
            messagebox.showerror("Check project","Choose a project with an installed toolkit and selected provider.")

    def project(self):
        if not self.destination.get().strip(): raise ValueError("Choose a project folder.")
        project=Project(self.name.get(),"",Path(self.destination.get()),
                        PROVIDERS.get(self.provider.get(),""),self.strong.get(),self.light.get(),self.escalation.get())
        project.validate()
        return project

    def start(self):
        try:
            project=self.project()
        except (ValueError,OSError) as error:
            messagebox.showerror("Check setup",str(error)); return
        self.running=True
        for field in self.fields: field.configure(state="disabled")
        self.select.configure(state="disabled")
        self.browse.configure(state="disabled")
        self.button.configure(state="disabled")
        self.configure.configure(state="disabled")
        self.status.set("Installing...")
        def worker():
            try:
                report=install_from_repository(project,log=lambda line:self.events.put(("log",line)))
                self.events.put(("done",report))
            except Exception as error:
                self.events.put(("error",str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=="log":
                self.log.configure(state="normal");self.log.insert("end",value+"\n");self.log.see("end");self.log.configure(state="disabled")
            else:
                self.running=False
                for field in self.fields: field.configure(state="normal")
                self.select.configure(state="readonly")
                self.browse.configure(state="normal");self.button.configure(state="normal")
                if hasattr(self,"configure"): self.configure.configure(state="normal")
                if kind=="error":
                    self.status.set("Setup needs attention");messagebox.showerror("Installation stopped",value)
                else:
                    complete=value["status"]=="installed"
                    self.status.set("Installed" if complete else "Setup incomplete")
                    details=(f"{value['agents']} agents and {value['project_skills']} project skills prepared.\n\n"
                             if "agents" in value and "project_skills" in value else "Installation did not complete.\n\n")
                    if complete:
                        details+="Restart your selected client and review INVENTORY.md.\nOptional CLIs and missing credentials are listed in installation.json."
                    else:
                        details+="Resolve the issues below and retry setup. Preserve existing files when merging.\nDetails: .agent-toolkit/installation.json."
                    if value["issues"]: details+="\n\nIssues:\n"+"\n".join(value["issues"])
                    if complete: messagebox.showinfo("Setup result",details)
                    else: messagebox.showwarning("Setup incomplete",details)
                    if complete and hasattr(self,"guide") and self.guide.get(): self.configure_tools()
        self.root.after(100,self.poll)

    def close(self):
        if self.running:
            messagebox.showinfo("Installation in progress","Wait for installation to finish before closing.")
        else: self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",type=Path,help="Check packaged UI and write a JSON result without installing")
    parser.add_argument("--install",action="store_true")
    parser.add_argument("--configure-tools",action="store_true",help="Open optional tool setup for an installed project")
    parser.add_argument("--project",type=Path)
    parser.add_argument("--name")
    parser.add_argument("--provider",choices=list(PROVIDERS.values()))
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    if args.self_test:
        root=tk.Tk();root.withdraw();wizard=Wizard(root)
        wizard.name.set("Example project");wizard.destination.set(str(Path.home()/"agent-toolkit-self-test"))
        if any(hasattr(wizard, name) for name in ["description", "repository", "ref"]):
            raise RuntimeError("The setup form must not contain description, repository or version inputs.")
        try:
            wizard.project()
        except ValueError:
            pass
        else:
            raise RuntimeError("The wizard must require an explicit provider selection.")
        for provider in PROVIDERS:
            wizard.provider.set(provider);wizard.change_provider();wizard.project()
        root.update_idletasks()
        with tempfile.TemporaryDirectory(prefix='toolkit-ui-check-') as directory:
            project=Path(directory)
            (project/'.agent-toolkit').mkdir()
            (project/'.agent-toolkit/project.json').write_text(json.dumps({'provider':'claude'}))
            from tool_runtime import RECIPES
            (project/'.agent-toolkit/registry.json').write_text(json.dumps({'tools':[{'id':name} for name in RECIPES]}))
            guided=ToolsWizard(root,project)
            guided.window.withdraw()
            root.update_idletasks()
            if len(guided.selected)!=5 or guided.persist.get():
                raise RuntimeError('Guided tools/credential consent controls failed')
            guided.window.destroy()
        args.self_test.write_text(json.dumps({"status":"passed","simplified_form":True,"guided_tools":hasattr(wizard,"guide"),"guided_window_constructed":True,"latest_stable_release":True,"provider_selection_required":True,"providers":list(PROVIDERS),"tk_version":tk.TkVersion}),encoding="utf-8")
        root.destroy();return 0
    if args.configure_tools:
        if not args.project: parser.error("--configure-tools requires --project")
        open_setup(args.project);return 0
    if args.install:
        if not args.project or not args.name or not args.provider:
            parser.error("--install requires --project, --name and --provider")
        project=Project(args.name,"",args.project,args.provider)
        log=lambda line: print(line,flush=True) if sys.stdout is not None else None
        result=install_from_repository(project,log=log)
        if args.report: args.report.write_text(json.dumps(result,indent=2),encoding="utf-8")
        return 0 if result["status"]=="installed" else 1
    root=tk.Tk();Wizard(root);root.mainloop();return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as error:
        if sys.stderr is not None: print("Installer: "+str(error),file=sys.stderr)
        sys.exit(1)
