# Architecture Viewer Refactor Plan

## Purpose
- Adapt the ConvNeXt/SettleNet architecture explorer from `thesis-architecture/demo.html` into a reusable component that can ship as a new section in the SettleNet prototype frontend.
- Remove hard-coded, single-file HTML/CSS/JS so the viewer fits the existing ES module workflow (`static/js`) and stylesheet structure (`static/css/prototype.css`).
- Preserve existing hover + pin interactions, accessibility cues, and module metadata while making it easy to add or swap architectures in the future.

## Source Review Highlights
### Thesis Architecture Demo
- Standalone document with inline `<style>` and `<script>`; assumes full-viewport layout (`stage`, `canvas`, `info-panel`).
- Architectures and tooltip copy are defined as large inline arrays (`convNeXtModuleBlueprint`, `settleNetModuleBlueprint`, etc.); module metadata is tightly coupled to DOM IDs inside the embedded SVGs.
- Viewer code handles: SVG loading, overlay rectangles, hover/pin events, responsive scaling through CSS variables, keyboard escape handling.
- Assets (SVGs, gifs, pngs) are referenced relatively under `architecture-section/` and need to be hosted inside SettleNet's static assets pipeline.

### SettleNet Frontend Prototype (`prototype-v3.html`)
- Uses `static/css/prototype.css` for all layout/theming and loads ES modules from `static/js/`.
- Existing JS modules (`main.js`, `ui.js`, `map.js`, `upload.js`) follow a feature-module pattern: each exports factories or helpers and is imported from the root `main.js` entry.
- Page sections follow a scrapbook aesthetic with defined spacing, `analysis-map` component, and a floating navigation system bound in `ui.js`.
- Templates live under `app/templates/`; static assets are served out of `app/static/`.

## Integration Goals
- Mount the architecture viewer as a new section near the end of the document, after the Weights & Biases report, without disturbing current sections.
- Ensure the viewer respects the overall theme (fonts, colors) and uses existing CSS tokens where possible.
- Make the feature lazy-load friendly (defer heavy SVG + gif loading until the section enters the viewport).
- Keep the module registry extensible so new architecture variants can be added with minimal code duplication.

## Proposed Refactor Breakdown
1. **Asset Migration**
   - Copy the required SVG diagrams and media assets into `app/static/media/architecture/` (create new directory) and adjust paths to go through `url_for('static', ...)` in templates.
   - Audit unused assets from the thesis demo; move only files referenced by module metadata.

2. **Data Layer Extraction**
   - Create `app/static/js/architecture/modules.js` exporting plain data objects for each architecture (ConvNeXt, ConvNeXt+U-Net, SettleNet).
   - Normalize module definitions: use consistent keys (`id`, `targets`, `title`, `summary`, `stats`, `details`, `media`, `margin`).
   - Store SVG file names in the registry along with viewer scaling factors.

3. **Viewer Logic Module**
   - Build `app/static/js/architecture/viewer.js` exporting a `createArchitectureViewer({ container, registry })` function.
   - Responsibilities: manage state (`activeModule`, `currentModel`), load SVG via `<object>`, register hover/pin interactions, update info panel.
   - Replace direct DOM queries with injected containers so the component can be instantiated wherever needed.
   - Support keyboard a11y (Escape to clear, focus traps) and provide cleanup hooks.

4. **Initializer Hook**
   - Add `app/static/js/architecture/index.js` that wires data + viewer module, handles dropdown changes, and optional IntersectionObserver to defer `createArchitectureViewer` until the section is visible.
   - Update `main.js` to conditionally import the architecture module (dynamic `import()` when the section exists) to avoid loading on pages that do not include it.

5. **Stylesheet Integration**
   - Move viewer styles into a dedicated partial `static/css/architecture-viewer.css` or scoped section within `prototype.css` using a prefix class such as `.architecture-viewer` to avoid conflicts.
   - Translate CSS variables to align with existing palette (e.g., reuse `--background-main`, `--text-primary`).
   - Ensure responsive breakpoints match existing layout conventions (640px, 960px already used in prototype CSS).

6. **Template Updates**
   - In `prototype-v3.html` (and later in the FastAPI template), add a new `<section id="architecture-viewer">` with the expected DOM skeleton: canvas container, info panel, dropdown, loading state.
   - Reference static assets via Jinja `url_for` when running inside Flask/FastAPI templates to ensure correct static path resolution.
   - Provide fallback copy for non-JS environments.

7. **Testing & QA Plan**
   - Manual checks: hover, click-to-pin, Escape key, switching architectures, resizing window (desktop/tablet/mobile breakpoints).
   - Validate lazy-loading: confirm module logic handles repeated visibility toggles without re-binding duplicate listeners.
   - Lighthouse/a11y pass on the new section to ensure keyboard focus indicators and aria labels remain intact.
   - Cross-browser smoke test (Chromium, Firefox) due to SVG focus styling differences.

8. **Documentation**
   - Update `README.md` with instructions on how to add new architecture definitions and where assets live.
   - Consider adding inline code comments in the JS modules pointing to SVG ID generation process (e.g., how to export IDs from Figma/Inkscape).

## Implementation Sequence
1. Scaffold directories (`static/js/architecture/`, `static/media/architecture/`, optional stylesheet).
2. Port assets and update paths.
3. Extract module metadata into `modules.js`.
4. Write viewer component (`viewer.js`) and initializer (`index.js`).
5. Integrate stylesheet and adjust theme tokens.
6. Update template section + include script (dynamic import).
7. Run formatting/linting, load page locally, exercise interactions, iterate on bugs.
8. Document new feature in README.

## Open Questions / Follow-ups
- Confirm whether final deployment uses FastAPI templates or the static prototype; adjust template syntax accordingly.
- Decide if we need to debounce hover events for performance on low-end devices (current code fires on every pointer enter/leave).
- Determine how SVG IDs will be maintained when diagrams change (potential pipeline to regenerate ID maps).
- Evaluate if module metadata should eventually come from backend JSON to keep content authoring outside the JS bundle.
