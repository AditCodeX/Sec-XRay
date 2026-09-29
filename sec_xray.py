import re
import os
import sys
import csv
import cmd
import urllib.parse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.rule import Rule
from rich import box

console = Console()

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import stealth_sync
    def apply_stealth(page):
        stealth_sync(page)
    STEALTH_AVAILABLE = True
except ImportError:
    try:
        from playwright_stealth.stealth import Stealth
        _stealth_instance = Stealth()
        def apply_stealth(page):
            _stealth_instance.apply_stealth_sync(page)
        STEALTH_AVAILABLE = True
    except Exception:
        STEALTH_AVAILABLE = False


def print_banner():
    # Top Tactical Bar
    top_grid = Table.grid(expand=True)
    top_grid.add_column(justify="left", style="bold cyan")
    top_grid.add_column(justify="right", style="dim")
    top_grid.add_row("[+] SEC_OPS // OFFENSIVE_RECON", "BUILD: [bold green]v1.0.0_STABLE[/] // ARCH: [bold white]HEADLESS_DOM[/]")

    # Slant Logo
    slant = r"""[bold white]
   _____            __  ______             
  / ___/___  _____  \ \/ / __ \____ ___  __
  \__ \/ _ \/ ___/   \  / /_/ / __ `/ / / /
 ___/ /  __/ /__     / / _, _/ /_/ / /_/ / 
/____/\___/\___/    /_/_/ |_|\__,_/\__, /  
                                  /____/   [/]"""

    # Center Content
    center_layout = Table.grid(expand=True)
    center_layout.add_column(justify="center")
    center_layout.add_row(Align.center(slant))
    center_layout.add_row("[bold cyan]PASSIVE & DYNAMIC SPA/JS RECONNAISSANCE ENGINE[/]\n")

    # Bottom Telemetry Badges (2 rows, 2 columns for clean terminal formatting)
    stealth_badge = "[bold green]Active (v2.0)[/]" if STEALTH_AVAILABLE else "[bold yellow]Disabled[/]"
    playwright_badge = "[bold green]Ready[/]" if PLAYWRIGHT_AVAILABLE else "[bold red]Not Installed[/]"

    bottom_grid = Table.grid(padding=(0, 3))
    bottom_grid.add_column(justify="left", style="dim")
    bottom_grid.add_column(justify="left")
    bottom_grid.add_column(justify="left", style="dim")
    bottom_grid.add_column(justify="left")

    bottom_grid.add_row(
        "[01] ENGINE  :", f"[bold cyan]Chromium Headless ({playwright_badge})[/]",
        "[02] EVASION :", stealth_badge
    )
    bottom_grid.add_row(
        "[03] CRAWL   :", "[bold white]Event-Driven DOM Trigger[/]",
        "[04] EXPORT  :", "[bold yellow]CSV + Postman v2.1[/]"
    )

    # Outer Tactical HUD Container
    main_table = Table.grid(expand=True, padding=(0, 0))
    main_table.add_column()
    main_table.add_row(top_grid)
    main_table.add_row(Rule(style="dim #334155"))
    main_table.add_row(center_layout)
    main_table.add_row(Rule(style="dim #334155"))
    main_table.add_row(Align.center(bottom_grid))

    hud_panel = Panel(
        main_table,
        border_style="bright_cyan",
        box=box.ROUNDED,
        padding=(1, 2)
    )

    console.print()
    console.print(hud_panel)
    console.print("[dim]Type [bold cyan]help[/] for command overview or [bold cyan]scan <target/list.txt>[/] to begin reconnaissance.[/]\n")


class SecXRayExtractor:
    def __init__(self):
        self.patterns = {
            "Endpoint": re.compile(r'["\'`]\s*((?:https?:)?//[^"\'`\s]+|/[a-zA-Z0-9_./?=&%\-]{2,})\s*["\'`]'),
            "Query Param": re.compile(r'[?&]([a-zA-Z0-9_\-]{2,})=|(?:\bparams|\bsearchParams)\.(?:append|set|get|has)\(["\'`]([a-zA-Z0-9_\-]{2,})["\'`]\)'),
            "JSON Key": re.compile(r'["\'`]([a-zA-Z0-9_\-]{2,})["\'`]\s*:|\b([a-zA-Z0-9_\-]{2,})\s*:\s*(?:["\'`{]|-?\d|true|false|null|\[)'),
            "HTML Script": re.compile(r'<script[^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)
        }

    def _clean_matches(self, matches):
        results = set()
        for match in matches:
            if isinstance(match, tuple):
                for group in match:
                    if group:
                        results.add(group.strip())
            else:
                if match:
                    results.add(match.strip())
        return list(results)

    def extract(self, text, is_html=False):
        findings = {"Endpoints": set(), "Query Params": set(), "JSON Keys": set(), "Secret Leaks": set()}
        contents_to_scan = self.patterns["HTML Script"].findall(text) if is_html else [text]
            
        for content in contents_to_scan:
            findings["Endpoints"].update(self._clean_matches(self.patterns["Endpoint"].findall(content)))
            findings["Query Params"].update(self._clean_matches(self.patterns["Query Param"].findall(content)))
            findings["JSON Keys"].update(self._clean_matches(self.patterns["JSON Key"].findall(content)))
            
            # Deteksi potensial secret/token yang bocor (Google API Key, AWS Key, JWT, Generic Secret)
            secret_patterns = [
                re.compile(r'\b(AIza[0-9A-Za-z-_]{33,37})\b'),
                re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
                re.compile(r'\b(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)\b'),
                re.compile(r'(?:["\'`]?([a-zA-Z0-9_-]*(?:secret|token|auth|bearer|key|password)[a-zA-Z0-9_-]*)["\'`]?)\s*[:=]\s*["\'`]([a-zA-Z0-9_\-.~+/=]{8,})["\'`]', re.IGNORECASE)
            ]
            
            ignore_keywords = {
                'label', 'aria', 'placeholder', 'tooltip', 'hint', 'title', 'desc', 'text',
                'i18n', 'intl', 'translation', 'locale', 'string', 'prompt', 'error', 'msg',
                'message', 'class', 'style', 'color', 'icon', 'button', 'input', 'field'
            }

            for pat in secret_patterns:
                matches = pat.findall(content)
                for m in matches:
                    if isinstance(m, tuple):
                        k, v = m[0], m[1] if len(m) > 1 else ""
                        k_lower = k.lower()
                        if any(ignored in k_lower for ignored in ignore_keywords):
                            continue
                        v_lower = v.lower()
                        if any(ignored in v_lower for ignored in ['aria', 'label', 'placeholder', 'translate', 'href']):
                            continue
                        if k and v:
                            findings["Secret Leaks"].add(f"{k}: {v}")
                    elif m:
                        findings["Secret Leaks"].add(m.strip())
            
            # Filter JSON keys sampah CSS / DOM
            clean_json_keys = set()
            junk_prefixes = ('-webkit', '-moz', '-ms', '-o', 'font-', 'margin', 'padding', 'border', 'flex', 'grid', 'text-', 'bg-', 'hover:', 'focus:')
            
            for key in findings["JSON Keys"]:
                k_lower = key.lower()
                if k_lower.startswith(junk_prefixes) or ' ' in key or len(key) < 2:
                    continue
                if k_lower in ('width', 'height', 'color', 'background', 'display', 'position', 'top', 'bottom', 'left', 'right', 'opacity', 'cursor', 'transition', 'transform', 'align', 'justify', 'overflow', 'z-index'):
                    continue
                clean_json_keys.add(key)
                
            findings["JSON Keys"] = clean_json_keys
            
        return findings


class SecXRayInteractive(cmd.Cmd):
    prompt = "⚡ sec-xray ❯ "

    def __init__(self):
        super().__init__()
        self.extractor = SecXRayExtractor()
        self.session_data = set()
        self.session_lock = threading.Lock()

    def preloop(self):
        print_banner()

    def _add_to_session(self, findings, source_target):
        new_count = 0
        if findings:
            with self.session_lock:
                for category, items in findings.items():
                    for item in items:
                        if len(str(item)) > 200:
                            continue
                        entry = (category, item, source_target)
                        if entry not in self.session_data:
                            self.session_data.add(entry)
                            new_count += 1
        return new_count

    def scan_with_playwright(self, url, deep_crawl=False):
        console.print(f"[bold cyan]🔍 Scanning Target:[/] [bold white]{url}[/]")
        if deep_crawl:
            console.print("   [magenta]⚡ Deep Crawl Mode Active:[/] Event-triggering all interactive elements...")
        else:
            console.print("   [dim]Monitoring network traffic & DOM lifecycle...[/]")
        
        total_added = 0
        visited_networks = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True
            )
            page = context.new_page()
            
            if STEALTH_AVAILABLE:
                apply_stealth(page)
            else:
                console.print("   [yellow]⚠ Warning:[/] Stealth mode inactive (playwright-stealth missing).")

            def on_response(response):
                nonlocal total_added
                resp_url = response.url
                
                if resp_url in visited_networks:
                    return
                visited_networks.add(resp_url)

                content_type = response.headers.get("content-type", "").lower()
                is_js = "javascript" in content_type or resp_url.endswith(".js")
                is_html = "text/html" in content_type

                if is_js or is_html:
                    try:
                        text = response.text()
                        findings = self.extractor.extract(text, is_html)
                        added = self._add_to_session(findings, resp_url)
                        if added > 0:
                            console.print(f"   [green]✓[/] [cyan]Intercepted:[/] [dim]{resp_url}[/] [bold green]+{added} items[/]")
                            total_added += added
                            
                        if is_js and not is_html:
                            self.fetch_source_map(resp_url)
                    except Exception:
                        pass

            page.on("response", on_response)

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                if deep_crawl:
                    try:
                        elements = page.query_selector_all("a, button, [role='button'], [role='link']")
                        console.print(f"   [magenta]⚡ Deep Crawl:[/] Found {len(elements)} clickable elements. Triggering (Max 15s)...")
                        
                        start_time = time.time()
                        clicked_count = 0
                        
                        for el in elements:
                            if time.time() - start_time > 15:
                                console.print("   [dim]Deep Crawl 15s limit reached, proceeding.[/]")
                                break
                            if clicked_count >= 50: 
                                break
                            try:
                                if el.is_visible() and el.is_enabled():
                                    el.click(timeout=1000, force=True) 
                                    clicked_count += 1
                                    time.sleep(0.05)
                            except Exception:
                                pass
                        
                        try:
                            page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                        
                        console.print(f"   [green]✓[/] [magenta]Deep Crawl:[/] Executed {clicked_count} DOM triggers successfully.")
                    except Exception as e:
                        console.print(f"   [dim yellow]Deep Crawl partial: {e}[/]")

                rendered_html = page.content()
                findings = self.extractor.extract(rendered_html, is_html=True)
                added = self._add_to_session(findings, url + " (Rendered DOM)")
                if added > 0:
                    console.print(f"   [green]✓[/] [cyan]DOM Tree:[/] Extracted [bold green]+{added} items[/] from rendered markup")
                    total_added += added
            except Exception as e:
                console.print(f"   [dim yellow]Navigation event: {e}[/]")
            
            browser.close()
        
        console.print(f"[bold green]✨ Complete:[/] Extracted [bold bright_green]{total_added}[/] findings from [bold white]{url}[/]\n")

    def fetch_source_map(self, js_url):
        if not REQUESTS_AVAILABLE:
            return
            
        map_url = js_url + ".map"
        try:
            resp = requests.get(map_url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    sources = data.get("sources", [])
                    if sources:
                        console.print(f"   [bold bright_yellow]★ Source Map Recovered:[/] [dim]{map_url}[/]")
                        map_findings = {"Endpoints": set()}
                        for src in sources:
                            clean_src = src.replace('webpack://', '').replace('../', '').strip()
                            if clean_src and '/' in clean_src:
                                map_findings["Endpoints"].add(clean_src)
                        
                        added = self._add_to_session(map_findings, map_url + " (Extracted SourceMap)")
                        if added > 0:
                            console.print(f"     [yellow]└─ Extracted [bold white]{added}[/] source paths from TypeScript/React tree[/]")
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    def _run_auto_export(self, target, is_batch=False):
        auto_filename = "sec_xray_findings"
        domain_name = ""
        
        if is_batch:
            base_name = os.path.basename(target)
            auto_filename = f"batch_{base_name.replace('.txt', '')}"
            domain_name = "batch_scan"
        elif target.startswith("http://") or target.startswith("https://"):
            parsed = urllib.parse.urlparse(target)
            domain_name = parsed.netloc.split(':')[0]
            if domain_name:
                auto_filename = domain_name
        else:
            base_name = os.path.basename(target)
            if base_name:
                auto_filename = base_name
                domain_name = base_name
                
        current_dir = os.getcwd()
        csv_export_path = os.path.join(current_dir, f"{auto_filename}.csv")
        postman_export_path = os.path.join(current_dir, f"{auto_filename}_postman.json")
                
        csv_count = self._export_csv(csv_export_path)
        postman_count = self._export_postman(domain_name, postman_export_path)

        summary_table = Table.grid(padding=(0, 2))
        summary_table.add_column(style="bold bright_cyan")
        summary_table.add_column(style="white")
        summary_table.add_row("CSV Dataset        :", f"[bold green]{csv_export_path}[/] ([bold white]{csv_count}[/] rows)")
        summary_table.add_row("Postman Collection :", f"[bold green]{postman_export_path}[/] ([bold white]{postman_count}[/] requests)")

        export_panel = Panel(
            summary_table,
            title="[bold green]📦 Auto-Export Complete[/]",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2)
        )
        console.print(export_panel)

    def do_scan(self, arg):
        """Scan domain, URL, file JS, atau .txt berisi daftar domain. Usage: scan <target> [--deep] [--threads N]"""
        if not arg:
            console.print("[bold red][!][/] Please specify a target. Example: [bold cyan]scan example.com[/] or [bold cyan]scan targets.txt[/]")
            return
            
        args_list = arg.split()
        target = args_list[0].strip()
        deep_crawl = '--deep' in args_list
        threads = 1
        if '--threads' in args_list:
            try:
                idx = args_list.index('--threads')
                threads = int(args_list[idx+1])
            except (ValueError, IndexError):
                console.print("[yellow][!][/] Invalid --threads value, falling back to 1.")
                
        if os.path.isfile(target) and target.lower().endswith('.txt'):
            batch_panel = Panel(
                f"[bold white]Target List File :[/] [cyan]{target}[/]\n"
                f"[bold white]Parallel Threads :[/] [bold bright_green]{threads}[/]\n"
                f"[bold white]Mode             :[/] [{'bold magenta]Deep Crawl' if deep_crawl else 'bold blue]Passive Intercept'}[/]",
                title="[bold bright_yellow]🚀 Batch Scanning Engine Active[/]",
                border_style="yellow",
                box=box.ROUNDED
            )
            console.print(batch_panel)
            
            if not PLAYWRIGHT_AVAILABLE:
                console.print("[bold red][!][/] Playwright is not installed. Required for web scanning.")
                return
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                console.print(f"[bold cyan]ℹ Found {len(urls)} target URLs to process.[/]\n")
                
                valid_urls = []
                for u in urls:
                    if not u.startswith("http://") and not u.startswith("https://"):
                        valid_urls.append("https://" + u)
                    else:
                        valid_urls.append(u)

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = [executor.submit(self.scan_with_playwright, u, deep_crawl) for u in valid_urls]
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            console.print(f"[bold red][!] Worker Exception:[/] {e}")
                            
                self.do_show("")
                self._run_auto_export(target, is_batch=True)
                return
            except Exception as e:
                console.print(f"[bold red][!] Batch Scan Error:[/] {e}")
                return

        is_local_file = False
        try:
            if os.path.isfile(target):
                is_local_file = True
        except:
            pass

        if not is_local_file and not target.startswith("http://") and not target.startswith("https://"):
            original_target = target
            target = "https://" + original_target
            try:
                requests.head(target, timeout=5)
            except Exception:
                target = "http://" + original_target

        if target.startswith("http://") or target.startswith("https://"):
            if not PLAYWRIGHT_AVAILABLE:
                console.print("[bold red][!][/] Playwright is not installed.")
                return
            
            self.scan_with_playwright(target, deep_crawl=deep_crawl)
            self.do_show("") 
        else:
            console.print(f"[bold cyan]📁 Scanning Local File:[/] [bold white]{target}[/]")
            try:
                with open(target, 'r', encoding='utf-8', errors='ignore') as f:
                    is_html = target.lower().endswith('.html')
                    findings = self.extractor.extract(f.read(), is_html)
                    added = self._add_to_session(findings, target)
                    console.print(f"[bold green]✓[/] Extracted [bold green]+{added}[/] findings from local file.")
                    self.do_show("")
            except Exception as e:
                console.print(f"[bold red][!] Error reading file:[/] {e}")
                return

        self._run_auto_export(target, is_batch=False)

    def do_show(self, arg):
        """Tampilkan data sesi saat ini. Usage: show [endpoints|secrets|params|keys]"""
        if not self.session_data:
            console.print(Panel("[yellow]Session cache is empty. Run [bold cyan]scan <target>[/] first.[/]", border_style="yellow", box=box.ROUNDED))
            return

        categories = {"Endpoints": set(), "Query Params": set(), "JSON Keys": set(), "Secret Leaks": set()}
        for cat, val, src in self.session_data:
            if cat in categories:
                categories[cat].add(val)

        filter_arg = arg.strip().lower()

        cat_map = {
            "endpoints": ("Endpoints", "🔗 Discovered Endpoints & Routes", "cyan"),
            "secrets": ("Secret Leaks", "🔥 Potential Secrets & Sensitive Leaks", "red"),
            "params": ("Query Params", "🔍 Extracted Query Parameters", "yellow"),
            "keys": ("JSON Keys", "📦 JSON & Request Payload Keys", "green")
        }

        if filter_arg in cat_map:
            cat_name, title, color = cat_map[filter_arg]
            items = sorted(categories[cat_name])
            if not items:
                console.print(f"[dim]No items found in {cat_name}.[/]")
                return

            detail_table = Table(title=title, box=box.ROUNDED, header_style=f"bold {color}", border_style=color)
            detail_table.add_column("#", justify="right", style="dim", width=5)
            detail_table.add_column("Value / Extracted String", style="white")

            for idx, it in enumerate(items, 1):
                detail_table.add_row(str(idx), it)

            console.print(detail_table)
            return

        summary_table = Table(title="📊 Reconnaissance Session Summary", box=box.ROUNDED, header_style="bold bright_cyan", border_style="bright_blue")
        summary_table.add_column("Category", style="bold")
        summary_table.add_column("Unique Findings", justify="right", style="bold bright_green")
        summary_table.add_column("Preview Samples (First 3)", style="dim")

        icons = {
            "Endpoints": "🔗 Endpoints",
            "Query Params": "🔍 Query Params",
            "JSON Keys": "📦 JSON Keys",
            "Secret Leaks": "🔥 Secret Leaks"
        }

        total_unique = 0
        for cat, items in categories.items():
            count = len(items)
            total_unique += count
            sample_str = ", ".join(list(sorted(items))[:3]) if items else "[dim]-[/]"
            summary_table.add_row(icons.get(cat, cat), str(count), sample_str)

        console.print(summary_table)

        if categories["Secret Leaks"]:
            secret_table = Table(title="🚨 High-Priority Sensitive Leaks Detected", box=box.HEAVY_EDGE, header_style="bold bright_red", border_style="red")
            secret_table.add_column("#", justify="right", style="dim", width=4)
            secret_table.add_column("Secret Token / Key-Value", style="bold bright_red")

            for idx, s in enumerate(sorted(categories["Secret Leaks"]), 1):
                secret_table.add_row(str(idx), s)

            console.print(secret_table)

        console.print(f"[dim]Total: [bold white]{total_unique}[/] unique findings. Run [bold cyan]show endpoints[/], [bold cyan]show secrets[/], [bold cyan]show params[/], or [bold cyan]show keys[/] for full listings.[/]\n")

    def _export_postman(self, batch_name, filepath):
        if not self.session_data:
            return 0

        # Pengelompokan berbasis Sumber File (Source Mapping)
        # Struktur: { source_url: { "endpoints": set(), "json_keys": set(), "query_params": set() } }
        source_map = {}
        for cat, val, src in self.session_data:
            if src not in source_map:
                source_map[src] = {"Endpoints": set(), "JSON Keys": set(), "Query Params": set()}
            if cat in source_map[src]:
                source_map[src][cat].add(val)

        items = []

        # Iterate per sumber file JS
        for source, data in source_map.items():
            endpoints = data["Endpoints"]
            json_keys = data["JSON Keys"]
            query_params = data["Query Params"]

            if not endpoints:
                continue

            # Menentukan base domain dari source file tersebut
            try:
                parsed_src = urllib.parse.urlparse(source)
                base_domain = f"{parsed_src.scheme}://{parsed_src.netloc}"
            except Exception:
                base_domain = "https://target_domain"
            
            # Jika domain gagal diurai (misal source dari local file)
            if base_domain == "://":
                base_domain = "https://target_domain"

            # Membentuk dummy JSON yang ukurannya masuk akal (Hanya keys dari file yg sama)
            dummy_json = {key: "" for key in sorted(json_keys)}
            raw_body = json.dumps(dummy_json, indent=2) if dummy_json else "{}"

            # Membentuk query string
            query_string = "&".join([f"{param}=" for param in sorted(query_params)])

            for ep in sorted(endpoints):
                # Format URL yang benar
                if ep.startswith("/"):
                    ep_url = f"{base_domain}{ep}"
                elif ep.startswith("//"):
                    ep_url = f"https:{ep}"
                else:
                    ep_url = ep

                if query_params and "?" not in ep_url:
                    ep_url = f"{ep_url}?{query_string}"
                elif query_params and "?" in ep_url:
                    if not ep_url.endswith("?"):
                        ep_url = f"{ep_url}&{query_string}"
                    else:
                        ep_url = f"{ep_url}{query_string}"
                
                # Auto-detect method: jika ada JSON keys, pakai POST. Jika kosong, pakai GET.
                http_method = "POST" if json_keys else "GET"
                
                item = {
                    "name": ep,
                    "request": {
                        "method": http_method,
                        "header": [
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "url": {
                            "raw": ep_url,
                            "protocol": ep_url.split("://")[0] if "://" in ep_url else "https",
                            "host": [ep_url.split("://")[-1].split("/")[0]],
                            "path": ep_url.split("://")[-1].split("/")[1:]
                        }
                    }
                }
                
                # Hanya sertakan Body JSON jika method POST
                if http_method == "POST":
                    item["request"]["body"] = {
                        "mode": "raw",
                        "raw": raw_body
                    }
                    
                items.append(item)

        if not items:
            return 0

        collection = {
            "info": {
                "name": f"Sec-XRay Recon: {batch_name}",
                "description": "Smart Auto-generated collection. Endpoints are mapped strictly with parameters found in the same JS file to prevent body over-stuffing.",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": items
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(collection, f, indent=4)
            return len(items)
        except Exception:
            return 0

    def _export_csv(self, filepath):
        if not self.session_data:
            return 0
        
        deduped_data = {}
        for cat, val, src in self.session_data:
            key = (cat, val)
            if key not in deduped_data:
                deduped_data[key] = set()
            deduped_data[key].add(src)

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Type', 'Value', 'Sources'])
                
                for (cat, val), sources in sorted(deduped_data.items()):
                    src_list = list(sources)
                    if len(src_list) > 3:
                        src_str = ", ".join(src_list[:3]) + f" ... (+{len(src_list)-3} others)"
                    else:
                        src_str = ", ".join(src_list)
                    writer.writerow([cat, val, src_str])
                    
            return len(deduped_data)
        except Exception:
            return 0

    def do_deepscan(self, arg):
        """Scan dengan mode Deep Crawl (otomatis trigger klik tombol & link). Usage: deepscan <target> [--threads N]"""
        if not arg:
            console.print("[bold red][!][/] Please specify a target. Example: [bold cyan]deepscan example.com[/] or [bold cyan]deepscan targets.txt[/]")
            return
        if '--deep' not in arg:
            arg = f"{arg} --deep"
        self.do_scan(arg)

    def do_help(self, arg):
        """Menampilkan panduan perintah, format target input, dan opsi flag Sec-XRay."""
        help_table = Table(title="⚡ Sec-XRay Interactive Command Reference", box=box.ROUNDED, header_style="bold bright_magenta", border_style="bright_magenta")
        help_table.add_column("Command", style="bold bright_cyan", width=24)
        help_table.add_column("Description", style="white")
        help_table.add_column("Example Usage", style="bright_yellow")

        help_table.add_row("scan <target>", "Passive & dynamic JS intercept scan", "scan target.com")
        help_table.add_row("scan <target> --deep", "Full scan with DOM button/link clicking", "scan target.com --deep")
        help_table.add_row("scan <list.txt> --threads N", "Batch scanning file .txt secara multi-thread", "scan subdomains.txt --threads 5")
        help_table.add_row("deepscan <target>", "Direct alias shortcut for deep DOM crawling", "deepscan target.com")
        help_table.add_row("deepscan <list.txt>", "Deep crawl massal ke seluruh list di file .txt", "deepscan subdomains.txt --threads 4")
        help_table.add_row("show", "Display overall summary & leaked credentials", "show")
        help_table.add_row("show <category>", "Drill-down: endpoints, secrets, params, keys", "show endpoints")
        help_table.add_row("clear", "Purge all current session findings from RAM", "clear")
        help_table.add_row("help / ?", "Show this command reference guide", "help")
        help_table.add_row("exit / quit", "Exit the interactive console shell", "exit")

        console.print(help_table)

        targets_table = Table(title="🎯 Supported Target Formats (Input Types)", box=box.ROUNDED, header_style="bold bright_green", border_style="green")
        targets_table.add_column("Target Type", style="bold bright_yellow", width=24)
        targets_table.add_column("Description & Behavior", style="white")
        targets_table.add_column("Command Example", style="bright_cyan")

        targets_table.add_row(
            "Domain / URL",
            "Target domain atau URL tunggal. Otomatis mencoba protokol HTTPS (fallback HTTP) & mencegat skrip dinamis.",
            "scan target.com"
        )
        targets_table.add_row(
            "Batch List File (.txt)",
            "File teks berisi daftar domain/URL (1 per baris). Otomatis memicu batch worker paralel dengan opsi [bold cyan]--threads N[/].",
            "scan subdomains.txt --threads 5"
        )
        targets_table.add_row(
            "Batch Deepscan (.txt)",
            "Menjalankan deep crawl event-driven secara masal ke seluruh domain di file teks (mengklik tombol/link di tiap domain).",
            "deepscan subdomains.txt --threads 4"
        )
        targets_table.add_row(
            "Local File (.js / .html)",
            "File bundle JavaScript atau HTML statis di folder lokal PC Anda. Mengekstrak langsung tanpa membuka browser.",
            "scan app.bundle.js"
        )

        console.print(targets_table)

        flags_table = Table(title="⚙️ Flags & Scan Options", box=box.ROUNDED, header_style="bold bright_cyan", border_style="cyan")
        flags_table.add_column("Flag / Option", style="bold bright_yellow", width=24)
        flags_table.add_column("Details & Behavior", style="white")

        flags_table.add_row(
            "--deep",
            "[bold magenta]Event-Driven DOM Crawler:[/] Memaksa browser mengklik tombol, dropdown, dan link untuk memicu Webpack lazy-loading & mengungkap endpoint API tersembunyi (Max 15s/page)."
        )
        flags_table.add_row(
            "--threads N",
            "[bold green]Multi-Browser Concurrency:[/] Menentukan jumlah instans Chromium yang berjalan bersamaan saat membaca daftar URL dari file [bold white].txt[/] (Default: 1)."
        )

        console.print(flags_table)

    def do_clear(self, arg):
        """Purge all findings in memory."""
        self.session_data = set()
        console.print("[bold green]✓[/] Session findings cleared from RAM.")

    def do_exit(self, arg):
        """Exit the application."""
        console.print("\n[bold bright_cyan]⚡ Sec-XRay terminated. Happy hunting![/]\n")
        return True
    
    def do_quit(self, arg):
        """Exit the application."""
        return self.do_exit(arg)


def main():
    try:
        SecXRayInteractive().cmdloop()
    except KeyboardInterrupt:
        console.print("\n[bold bright_cyan]⚡ Sec-XRay terminated. Happy hunting![/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
