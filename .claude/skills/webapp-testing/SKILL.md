---
name: webapp-testing
description: Test web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing screenshots, and viewing browser logs. Use when testing the website or debugging UI issues.
---

# Web Application Testing with Playwright

Test the website using Playwright browser automation. Verify functionality, debug UI issues, capture screenshots, and inspect browser state.

---

## When This Skill Activates

- Testing website functionality
- Debugging UI behavior
- Capturing screenshots for documentation
- Verifying responsive design
- Checking dark/light mode
- Testing user flows (navigation, forms)
- Investigating browser console errors

---

## Project Context

**Website stack:**
- React 19 + Vite 6.2
- Tailwind CSS v4
- Dev server: `npm run dev` (typically port 5173)
- Build: `npm run build` → `dist/`

**Key pages to test:**
- Landing page (`/`)
- Charity list
- Individual charity detail pages
- Methodology page
- About page

**Theme states:**
- Light mode / Dark mode toggle
- Brand variants (amal / third-bucket)

---

## Testing Workflow

### 1. Reconnaissance First

Before automating, understand the page:

```python
# Take screenshot to see current state
page.screenshot(path="screenshot.png")

# Get page title
print(page.title())

# Wait for dynamic content
page.wait_for_load_state('networkidle')

# Inspect DOM structure
print(page.content())
```

### 2. Decision Tree

**Is the dev server running?**
- Yes → Connect directly to `http://localhost:5173`
- No → Start it first, then connect

**Is content static or dynamic?**
- Static HTML → Read files directly for selectors
- Dynamic (React) → Wait for `networkidle` before inspecting

**What are you testing?**
- Visual appearance → Screenshot
- Functionality → Automated interactions
- Errors → Console log capture

---

## Playwright Patterns

### Basic Script Structure

```python
from playwright.sync_api import sync_playwright

def test_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("http://localhost:5173")
            page.wait_for_load_state('networkidle')

            # Your test logic here

        finally:
            browser.close()

if __name__ == "__main__":
    test_page()
```

### Waiting for Dynamic Content

```python
# Wait for network to settle (React hydration)
page.wait_for_load_state('networkidle')

# Wait for specific element
page.wait_for_selector('[data-testid="charity-card"]')

# Wait for text to appear
page.wait_for_selector('text=Loading...', state='hidden')
```

### Element Selection

**Prefer readable selectors:**

```python
# By role (best for accessibility)
page.get_by_role("button", name="Toggle theme")

# By text content
page.get_by_text("View Details")

# By test ID (if available)
page.get_by_test_id("charity-card")

# By CSS (fallback)
page.locator(".charity-card")

# By combined selectors
page.locator("article").filter(has_text="Islamic Relief")
```

### Common Actions

```python
# Click
page.get_by_role("button", name="Submit").click()

# Type
page.get_by_label("Email").fill("test@example.com")

# Select dropdown
page.get_by_role("combobox").select_option("option-value")

# Hover
page.get_by_text("Menu").hover()

# Screenshot
page.screenshot(path="test-result.png", full_page=True)
```

### Assertions

```python
from playwright.sync_api import expect

# Element is visible
expect(page.get_by_text("Welcome")).to_be_visible()

# Element has text
expect(page.locator("h1")).to_have_text("Charity Evaluations")

# Element count
expect(page.locator(".charity-card")).to_have_count(10)

# URL
expect(page).to_have_url("http://localhost:5173/charity/123")

# Title
expect(page).to_have_title("Good Measure Giving")
```

---

## Test Scenarios

### Theme Toggle

```python
def test_theme_toggle():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:5173")
        page.wait_for_load_state('networkidle')

        # Check initial state
        body = page.locator("body")
        initial_bg = body.evaluate("el => getComputedStyle(el).backgroundColor")

        # Toggle theme
        page.get_by_role("button", name="Toggle theme").click()

        # Verify change
        new_bg = body.evaluate("el => getComputedStyle(el).backgroundColor")
        assert initial_bg != new_bg, "Theme should change"

        browser.close()
```

### Responsive Design

```python
def test_mobile_view():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Mobile viewport
        page = browser.new_page(viewport={"width": 375, "height": 667})
        page.goto("http://localhost:5173")
        page.wait_for_load_state('networkidle')

        # Check mobile menu is present
        expect(page.get_by_role("button", name="Menu")).to_be_visible()

        # Desktop navbar should be hidden
        expect(page.locator("nav.desktop-nav")).to_be_hidden()

        page.screenshot(path="mobile-view.png")
        browser.close()
```

### Charity Card Navigation

```python
def test_charity_navigation():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:5173")
        page.wait_for_load_state('networkidle')

        # Find first charity card and click
        first_card = page.locator(".charity-card").first
        charity_name = first_card.locator("h3").text_content()
        first_card.click()

        # Should navigate to detail page
        page.wait_for_load_state('networkidle')
        expect(page.locator("h1")).to_contain_text(charity_name)

        browser.close()
```

### Console Error Capture

```python
def test_no_console_errors():
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Capture console errors
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        page.goto("http://localhost:5173")
        page.wait_for_load_state('networkidle')

        # Navigate through pages
        page.get_by_text("Methodology").click()
        page.wait_for_load_state('networkidle')

        browser.close()

    assert len(errors) == 0, f"Console errors found: {errors}"
```

---

## Debugging Tips

### Visual Debugging

```python
# Run with browser visible
browser = p.chromium.launch(headless=False, slow_mo=500)

# Pause for manual inspection
page.pause()

# Screenshot on failure
try:
    # test code
except Exception as e:
    page.screenshot(path="failure.png")
    raise
```

### Network Inspection

```python
# Log all requests
page.on("request", lambda req: print(f">> {req.method} {req.url}"))
page.on("response", lambda res: print(f"<< {res.status} {res.url}"))

# Wait for specific API call
with page.expect_response("**/api/charities") as response_info:
    page.goto("http://localhost:5173")
response = response_info.value
print(response.json())
```

### Trace Recording

```python
# Record trace for debugging
context = browser.new_context()
context.tracing.start(screenshots=True, snapshots=True)

page = context.new_page()
# ... run tests ...

context.tracing.stop(path="trace.zip")
# View with: npx playwright show-trace trace.zip
```

---

## Server Management

### Start Dev Server for Testing

```bash
# Terminal 1: Start server
cd website && npm run dev

# Terminal 2: Run tests
python test_script.py
```

### Programmatic Server Start

```python
import subprocess
import time

def with_server(test_func):
    """Decorator to start/stop dev server"""
    def wrapper():
        # Start server
        server = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="website",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(5)  # Wait for server to start

        try:
            test_func()
        finally:
            server.terminate()
            server.wait()

    return wrapper

@with_server
def test_homepage():
    # Test runs with server available
    pass
```

---

## Quick Reference

### Viewport Sizes

| Device | Width | Height |
|--------|-------|--------|
| Mobile | 375 | 667 |
| Tablet | 768 | 1024 |
| Desktop | 1280 | 720 |
| Large | 1920 | 1080 |

### Common Waits

```python
page.wait_for_load_state('networkidle')  # All requests done
page.wait_for_load_state('domcontentloaded')  # DOM ready
page.wait_for_selector('selector')  # Element exists
page.wait_for_timeout(1000)  # Hard wait (avoid if possible)
```

### Screenshot Options

```python
page.screenshot(
    path="screenshot.png",
    full_page=True,          # Entire scrollable page
    # OR
    clip={"x": 0, "y": 0, "width": 500, "height": 500}  # Specific area
)
```

---

## Test Checklist

Before shipping:

- [ ] Homepage loads without console errors
- [ ] Theme toggle works (light ↔ dark)
- [ ] Mobile responsive (375px viewport)
- [ ] Tablet responsive (768px viewport)
- [ ] Charity cards render correctly
- [ ] Charity detail pages load
- [ ] Navigation works (all links)
- [ ] Images load (no broken images)
- [ ] No accessibility errors (axe-core)
