"""
Victoria - REA Web Inspector
Reverse engineers websites and web applications:
- Discovers API endpoints (REST, GraphQL, WebSocket)
- Detects tech stack, frameworks, UI libraries, and analytics
- Extracts DOM structure, form definitions, and design tokens
- Analyzes JavaScript bundles for hidden routes and configs
- Supports Playwright/CDP live traffic interception when available
"""

import re
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from rich.console import Console

console = Console()


@dataclass
class ApiEndpoint:
    url: str
    method: str = "GET"
    category: str = "REST"  # REST, GraphQL, WebSocket, Asset
    parameters: list[str] = field(default_factory=list)
    auth_required: bool = False
    headers: dict[str, str] = field(default_factory=dict)
    sample_response: Optional[str] = None


@dataclass
class WebTeardownResult:
    target_url: str
    status_code: int = 0
    title: str = ""
    description: str = ""
    tech_stack: dict[str, list[str]] = field(default_factory=dict)
    endpoints: list[dict[str, Any]] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    design_tokens: dict[str, list[str]] = field(default_factory=dict)
    meta_tags: dict[str, str] = field(default_factory=dict)
    websocket_urls: list[str] = field(default_factory=list)
    graphql_endpoints: list[str] = field(default_factory=list)
    potential_secrets: list[str] = field(default_factory=list)
    intercepted_traffic: list[dict[str, Any]] = field(default_factory=list)


class WebInspector:
    """
    Website & Web Application Reverse Engineering Engine.
    """

    def __init__(self, timeout: int = 15, verify_ssl: Optional[bool] = None):
        self.timeout = timeout
        # TLS verification is configurable (config: `rea.verify_ssl`).
        # Defaults to False to preserve the ability to scan dev/staging hosts
        # with self-signed certs, but can be turned on for hardened scanning.
        if verify_ssl is None:
            try:
                from victoria.config import get_config
                verify_ssl = bool(get_config().get("rea.verify_ssl", False))
            except Exception:
                verify_ssl = False
        self.verify_ssl = verify_ssl
        if not self.verify_ssl:
            console.print(
                "[yellow]⚠️ REA web scan is running with TLS verification DISABLED "
                "(set `rea.verify_ssl: true` in config to enable).[/yellow]"
            )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch_url(self, url: str) -> tuple[int, str, dict[str, str]]:
        """Fetch URL using httpx if available, else urllib with SSL ignore."""
        if httpx is not None:
            with httpx.Client(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
                verify=self.verify_ssl,
            ) as client:
                resp = client.get(url)
                return resp.status_code, resp.text, dict(resp.headers)

        # Standard library urllib fallback
        req = urllib.request.Request(url, headers=self.headers)
        ctx = ssl.create_default_context()
        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as response:
            status = response.getcode()
            content = response.read().decode("utf-8", "ignore")
            headers = dict(response.info())
            return status, content, headers

    def inspect(self, url: str, deep_crawl: bool = True) -> WebTeardownResult:
        """
        Reverse engineer a website target.

        Args:
            url: Target website URL (http or https)
            deep_crawl: Whether to fetch and scan linked JS bundles for hidden APIs

        Returns:
            WebTeardownResult dataclass with comprehensive findings.
        """
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        console.print(f"[cyan]🔍 Reverse engineering website: {url}[/cyan]")
        result = WebTeardownResult(target_url=url)

        try:
            status_code, html_content, resp_headers = self._fetch_url(url)
            result.status_code = status_code

            # 1. Tech Stack Detection (from headers & HTML)
            result.tech_stack = self._detect_tech_stack(html_content, resp_headers)

            # 2. Extract Metadata & Meta tags
            result.title = self._extract_title(html_content)
            result.meta_tags = self._extract_meta_tags(html_content)
            result.description = result.meta_tags.get("description", "")

            # 3. Extract Scripts and Styles
            result.scripts = self._extract_resources(html_content, url, "script", "src")
            result.stylesheets = self._extract_resources(html_content, url, "link", "href")

            # 4. Extract Forms and Input Schemas
            result.forms = self._extract_forms(html_content, url)

            # 5. Extract Design Tokens (fonts, colors, CSS vars)
            result.design_tokens = self._extract_design_tokens(html_content)

            # 6. Extract Direct APIs from HTML
            endpoints, websockets, graphqls, secrets = self._extract_apis_and_secrets(html_content, url)
            result.endpoints.extend([asdict(e) for e in endpoints])
            result.websocket_urls.extend(websockets)
            result.graphql_endpoints.extend(graphqls)
            result.potential_secrets.extend(secrets)

            # 7. Deep Crawl Linked JS Bundles (Up to 5 bundles)
            if deep_crawl and result.scripts:
                console.print(f"[dim]⚡ Scanning {min(5, len(result.scripts))} JavaScript bundles for API routes...[/dim]")
                for script_url in result.scripts[:5]:
                    try:
                        s_status, s_text, _ = self._fetch_url(script_url)
                        if s_status == 200:
                            js_endpoints, js_ws, js_gql, js_sec = self._extract_apis_and_secrets(s_text, url)
                            for ep in js_endpoints:
                                ep_dict = asdict(ep)
                                if ep_dict not in result.endpoints:
                                    result.endpoints.append(ep_dict)
                            result.websocket_urls.extend([w for w in js_ws if w not in result.websocket_urls])
                            result.graphql_endpoints.extend([g for g in js_gql if g not in result.graphql_endpoints])
                            result.potential_secrets.extend([s for s in js_sec if s not in result.potential_secrets])
                    except Exception:
                        continue

            # 8. Live Traffic Interception via Playwright / Chrome DevTools (if available)
            if deep_crawl:
                self._intercept_with_playwright(url, result)

        except Exception as e:
            console.print(f"[red]❌ Error inspecting web target {url}: {e}[/red]")
            result.description = f"Error during inspection: {str(e)}"

        console.print(
            f"[green]✅ Web teardown complete: {len(result.endpoints)} endpoints, "
            f"{sum(len(v) for v in result.tech_stack.values())} tech components detected.[/green]"
        )
        return result

    def _intercept_with_playwright(self, url: str, result: WebTeardownResult):
        """Live network interception using Playwright headless Chromium & CDP."""
        if sync_playwright is None:
            return

        try:
            console.print("[dim]🌐 Launching headless browser for live network traffic & CDP sniffing...[/dim]")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                page = browser.new_page()

                def on_request(request):
                    req_type = request.resource_type
                    req_url = request.url
                    if req_type in ["xhr", "fetch", "websocket"]:
                        headers = request.headers
                        auth_present = "authorization" in headers or "cookie" in headers
                        result.intercepted_traffic.append({
                            "url": req_url,
                            "method": request.method,
                            "type": req_type,
                            "has_auth": auth_present,
                        })
                        parsed = urllib.parse.urlparse(req_url)
                        if parsed.path and parsed.path not in ["/"]:
                            ep = ApiEndpoint(
                                url=req_url,
                                method=request.method,
                                category="XHR/Fetch" if req_type != "websocket" else "WebSocket",
                                auth_required=auth_present,
                            )
                            ep_dict = asdict(ep)
                            if ep_dict not in result.endpoints:
                                result.endpoints.append(ep_dict)

                page.on("request", on_request)

                try:
                    page.goto(url, wait_until="networkidle", timeout=12000)
                except Exception:
                    pass

                if not result.title:
                    result.title = page.title()

                browser.close()
                console.print(f"[green]✅ Playwright intercepted {len(result.intercepted_traffic)} live network calls.[/green]")
        except Exception as e:
            console.print(f"[dim]Playwright live interception note: {e}[/dim]")

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_meta_tags(self, html: str) -> dict[str, str]:
        tags = {}
        pattern = re.compile(r"<meta\s+([^>]+)>", re.IGNORECASE)
        for match in pattern.finditer(html):
            tag_str = match.group(1)
            name_match = re.search(r'(?:name|property)=["\']([^"\']+)["\']', tag_str, re.IGNORECASE)
            content_match = re.search(r'content=["\']([^"\']+)["\']', tag_str, re.IGNORECASE)
            if name_match and content_match:
                tags[name_match.group(1).lower()] = content_match.group(1)
        return tags

    def _extract_resources(self, html: str, base_url: str, tag: str, attr: str) -> list[str]:
        pattern = re.compile(rf"<{tag}[^>]+{attr}=[\"']([^\"']+)[\"']", re.IGNORECASE)
        urls = []
        for match in pattern.finditer(html):
            raw = match.group(1)
            full_url = urllib.parse.urljoin(base_url, raw)
            if full_url not in urls:
                urls.append(full_url)
        return urls

    def _extract_forms(self, html: str, base_url: str) -> list[dict[str, Any]]:
        forms = []
        form_matches = re.finditer(r"<form\s*([^>]*)>(.*?)</form>", html, re.IGNORECASE | re.DOTALL)
        for fm in form_matches:
            attrs_str = fm.group(1)
            body_str = fm.group(2)

            action_match = re.search(r'action=["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
            method_match = re.search(r'method=["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)

            action = urllib.parse.urljoin(base_url, action_match.group(1)) if action_match else base_url
            method = method_match.group(1).upper() if method_match else "GET"

            inputs = []
            input_matches = re.finditer(r"<input\s+([^>]+)>", body_str, re.IGNORECASE)
            for im in input_matches:
                attr = im.group(1)
                name_m = re.search(r'name=["\']([^"\']+)["\']', attr, re.IGNORECASE)
                type_m = re.search(r'type=["\']([^"\']+)["\']', attr, re.IGNORECASE)
                inputs.append({
                    "name": name_m.group(1) if name_m else "unnamed",
                    "type": type_m.group(1) if type_m else "text",
                })

            forms.append({"action": action, "method": method, "inputs": inputs})
        return forms

    def _extract_design_tokens(self, html: str) -> dict[str, list[str]]:
        tokens: dict[str, list[str]] = {
            "colors": [],
            "fonts": [],
            "css_variables": [],
        }

        # Colors (Hex codes)
        hex_colors = set(re.findall(r"#(?:[0-9a-fA-F]{3}){1,2}\b", html))
        tokens["colors"] = sorted(list(hex_colors))[:20]

        # Fonts
        font_matches = set(re.findall(r"font-family\s*:\s*([^;}\"'>]+)", html, re.IGNORECASE))
        cleaned_fonts = set()
        for f in font_matches:
            for part in f.split(","):
                p = part.strip().strip("'\"")
                if p and not p.startswith("var("):
                    cleaned_fonts.add(p)
        tokens["fonts"] = sorted(list(cleaned_fonts))[:10]

        # CSS Variables (--primary-color, etc.)
        css_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", html))
        tokens["css_variables"] = sorted(list(css_vars))[:25]

        return tokens

    def _detect_tech_stack(self, html: str, headers: dict[str, str]) -> dict[str, list[str]]:
        stack: dict[str, list[str]] = {
            "frameworks": [],
            "ui_libraries": [],
            "bundlers": [],
            "analytics": [],
            "server_and_cdn": [],
        }

        # Server headers
        server = headers.get("server", "")
        if "cloudflare" in server.lower() or "cf-ray" in headers:
            stack["server_and_cdn"].append("Cloudflare")
        if "vercel" in headers or "x-vercel-id" in headers:
            stack["server_and_cdn"].append("Vercel")
        if "netlify" in headers:
            stack["server_and_cdn"].append("Netlify")
        if server:
            stack["server_and_cdn"].append(server)

        # Frameworks
        if "__NEXT_DATA__" in html or "/_next/" in html:
            stack["frameworks"].append("Next.js")
            stack["frameworks"].append("React")
        elif "react" in html.lower() or "_react" in html:
            stack["frameworks"].append("React")

        if "__NUXT__" in html or "/_nuxt/" in html:
            stack["frameworks"].append("Nuxt.js")
            stack["frameworks"].append("Vue.js")
        elif "vue" in html.lower() or "data-v-" in html:
            stack["frameworks"].append("Vue.js")

        if "ng-version" in html or "ng-app" in html:
            stack["frameworks"].append("Angular")
        if "svelte" in html.lower() or "__svelte" in html:
            stack["frameworks"].append("Svelte")
        if "astro" in html.lower():
            stack["frameworks"].append("Astro")
        if "wp-content" in html or "wordpress" in html.lower():
            stack["frameworks"].append("WordPress")
        if "shopify" in html.lower():
            stack["frameworks"].append("Shopify")

        # UI Libraries
        if "tailwindcss" in html.lower() or re.search(r'class="[^"]*(?:flex|grid|p-\d|m-\d|text-\w+)', html):
            stack["ui_libraries"].append("Tailwind CSS")
        if "bootstrap" in html.lower():
            stack["ui_libraries"].append("Bootstrap")
        if "material-ui" in html.lower() or "mui" in html.lower():
            stack["ui_libraries"].append("Material UI (MUI)")
        if "chakra" in html.lower():
            stack["ui_libraries"].append("Chakra UI")
        if "radix" in html.lower():
            stack["ui_libraries"].append("Radix UI")

        # Bundlers
        if "webpack" in html.lower():
            stack["bundlers"].append("Webpack")
        if "vite" in html.lower() or "/@vite/" in html:
            stack["bundlers"].append("Vite")

        # Analytics
        if "google-analytics.com" in html or "googletagmanager.com" in html or "gtag" in html:
            stack["analytics"].append("Google Analytics / GTM")
        if "segment.com" in html or "analytics.js" in html:
            stack["analytics"].append("Segment")
        if "mixpanel" in html.lower():
            stack["analytics"].append("Mixpanel")
        if "hotjar" in html.lower():
            stack["analytics"].append("Hotjar")
        if "posthog" in html.lower():
            stack["analytics"].append("PostHog")

        # Deduplicate
        for k in stack:
            stack[k] = list(dict.fromkeys(stack[k]))

        return stack

    def _extract_apis_and_secrets(
        self, text: str, base_url: str
    ) -> tuple[list[ApiEndpoint], list[str], list[str], list[str]]:
        endpoints: list[ApiEndpoint] = []
        websockets: list[str] = []
        graphqls: list[str] = []
        secrets: list[str] = []

        # 1. REST API endpoint pattern matches: /api/v1/..., /api/..., /v1/...
        api_pattern = re.compile(r'["\'](/(?:api|v[0-9]+|rest|auth|users|products|search|graphql)/[a-zA-Z0-9_\-\./?=&%]+)["\']')
        for match in api_pattern.finditer(text):
            path = match.group(1)
            full = urllib.parse.urljoin(base_url, path)
            endpoints.append(ApiEndpoint(url=full, method="GET", category="REST"))

        # 2. WebSocket URLs
        ws_pattern = re.compile(r'["\'](wss?://[a-zA-Z0-9_\-\.:/]+)["\']')
        for match in ws_pattern.finditer(text):
            websockets.append(match.group(1))

        # 3. GraphQL matches
        if "/graphql" in text or "query " in text or "mutation " in text:
            gql_matches = re.findall(r'["\']([^"\']*/graphql[^"\']*)["\']', text)
            for m in gql_matches:
                full_gql = urllib.parse.urljoin(base_url, m)
                graphqls.append(full_gql)

        # 4. Secrets / API Key patterns (e.g., Stripe, Firebase, AWS, generic tokens)
        secret_patterns = [
            (r'pk_(?:live|test)_[0-9a-zA-Z]{24,}', "Stripe Public Key"),
            (r'AIza[0-9A-Za-z\\-_]{35}', "Google/Firebase API Key"),
            (r'ghp_[0-9a-zA-Z]{36}', "GitHub Personal Access Token"),
            (r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}', "JWT Token"),
        ]
        for pattern, label in secret_patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                secrets.append(f"{label}: {m[:10]}...{m[-4:]}")

        # Deduplicate endpoints by URL
        seen_urls = set()
        deduped_endpoints = []
        for ep in endpoints:
            if ep.url not in seen_urls:
                seen_urls.add(ep.url)
                deduped_endpoints.append(ep)

        return deduped_endpoints, list(set(websockets)), list(set(graphqls)), list(set(secrets))

    def generate_api_client_code(self, result: WebTeardownResult, language: str = "python") -> str:
        """
        Generate a ready-to-run reconstructed API client SDK for the reverse-engineered website.
        """
        if language.lower() == "python":
            code = [
                f"# Reconstructed API Client for {result.target_url}",
                "# Auto-generated by Project Victoria REA Engine",
                "import requests",
                "from typing import Optional, Dict, Any\n",
                "class ReconstructedClient:",
                f"    BASE_URL = '{result.target_url.rstrip('/')}'\n",
                "    def __init__(self, auth_token: Optional[str] = None):",
                "        self.session = requests.Session()",
                "        self.session.headers.update({",
                "            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',",
                "            'Accept': 'application/json, text/plain, */*',",
                "        })",
                "        if auth_token:",
                "            self.session.headers['Authorization'] = f'Bearer {auth_token}'\n",
            ]

            for i, ep in enumerate(result.endpoints[:15]):
                parsed = urllib.parse.urlparse(ep["url"])
                slug = re.sub(r"[^a-zA-Z0-9_]", "_", parsed.path.strip("/")).strip("_")
                func_name = f"api_{slug}" if slug else f"endpoint_{i}"
                code.extend([
                    f"    def {func_name}(self, params: Optional[Dict[str, Any]] = None) -> Any:",
                    f"        \"\"\"Call {ep['method']} {parsed.path}\"\"\"",
                    f"        url = f'{{self.BASE_URL}}{parsed.path}'",
                    f"        response = self.session.request('{ep['method']}', url, params=params)",
                    "        response.raise_for_status()",
                    "        return response.json() if 'application/json' in response.headers.get('content-type', '') else response.text\n",
                ])

            return "\n".join(code)

        # Default TypeScript client
        return "// TypeScript client generation available upon request"
