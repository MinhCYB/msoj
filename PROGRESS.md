# MSOJ Visual Refresh — Engineering Handoff

Status: engineering implementation and available local QA complete; owner Visual Acceptance not claimed. No commit, deployment or production-data mutation. Native lecture migration and fixture accounts were exercised only in disposable local QA databases.

## Recovery

Continued the existing session, not a new implementation. The tool TODO was 5/6 complete with handoff active. `TASKS.json` and `PROGRESS.md` did not exist in the repository when searched; these records were created for the requested recovery handoff. Inspected `git status --short`, source diff and `/tmp/msoj-visual-refresh/` artifacts. Preserved all existing uncommitted changes, including pre-existing template differences; no reset, checkout or discard.

Only the interrupted modern-reader post-fix browser check was rerun. Existing 52-state screenshot/contract matrix, 44-state accessibility matrix and 120 breakpoint checks were reused. The active Playwright connection remained usable. No OMP/provider/model configuration changed.

## Reference and Design DNA

- Required `docs/design/references/motionsites-original.md` is 0 bytes. It supplies no prompt specification; no claims about its motion/responsive instructions are made.
- Required screenshot is 1280×956. Observed: small floating white navigation capsule and separate dark sign-in capsule; central two-line dot-matrix headline; restrained sans-serif navigation/support copy; a dark elliptical cavity framed by pink/lavender light; brighter upper background with scattered matrix characters; white pill CTA; thin compact metric strip below. Central bright-on-dark text creates the hierarchy, not surface clutter.
- **ADOPT:** floating/pill navigation, Inter UI typography paired with short dot-matrix accents, generous landing whitespace, rounded controls, thin surface borders and restrained depth.
- **ADAPT:** retain MSOJ functional layouts/IA, including the two-column landing and workspace. Recreate ambient lavender/rose light using original static CSS radial gradients, not Motionsites media. Landing receives the strongest treatment; prose, tables, code and mathematics remain quiet. Existing light/dark palette and semantic verdict/rating colors remain authoritative.
- **REJECT:** reference logo, partner brands, trust claims, metrics, video and continuous matrix animation; pixel typography for prose/code/math; background effects that obscure task content.
- Motion/mobile are MSOJ decisions, not measurements from a still screenshot: landing-only 600ms opacity/12px entrance, 100ms aside delay; 160ms control transitions with `cubic-bezier(0.22, 1, 0.36, 1)`; no continuous background animation. Reduced-motion disables entrance and shared control motion. Mobile navigation retains its existing drawer mechanics with inline submenus, keyboard open/close and readable target sizes; switches at 1100px to prevent navigation/account overlap.

## Completed Areas

- Landing: display accent, ambient background, eyebrow pill, CTA pills, rounded explore/features/pricing surfaces; original content and routes retained.
- Shared navigation/shell: floating capsule, Inter, Doto wordmark, active state/focus, mobile menu cascade repair, accessible settings/theme/language controls, explicit Auto option, skip-to-content and footer contrast.
- Problems, Submissions, Contests, status/Judge presentation: inherited consistent shell, controls, tabs and sideboxes; filtering/list layouts and verdict/rating/chart palettes unchanged.
- Roadmap index and knowledge map: rounded cards and status pills; existing lazy branch opening/collapse retained.
- Workspace: semantic token aliases replace duplicated theme palettes; pill actions; existing edge-to-edge desktop panes retained; keyboard-scrollable statement and separate resize/collapse semantics. No Judge, submission or AI workflow change.
- Public users, blog listing, classic/modern reader, login/OAuth, about and runtimes: shared style propagation; scoped comment metadata contrast, image alternative text, prose-link underlines and OAuth accessible name.
- Stylesheet/JS asset versions updated. Blog Inter CDN request removed in favor of local font ownership.

## Tokens and Owners

`resources/academic-ink.scss` remains the semantic owner:

- `--ms-font-ui`: Inter + existing system fallbacks.
- `--ms-font-display`: Doto + monospace fallback; only short display/brand accents.
- `--ms-radius-sm`: 10px; `--ms-radius-panel`: 18px; `--ms-radius-pill`: 999px.
- `--ms-duration-fast`: 160ms; `--ms-ease`: cubic-bezier(0.22, 1, 0.36, 1).
- Paired light/dark ambient and shadow tokens; existing text/link/button/focus and semantic palette retained.

Existing owners changed: `base.scss`, `navbar.scss`, `widgets.scss`, `academic-ink.scss`, `roadmap.scss`, `landing.css`, `problem-workspace.css`, `blog-modern.scss`, `blog-post.scss`, `comments.scss`; bounded interaction changes in `common.js` and `problem-workspace.js`. Obsolete duplicated landing styles removed from the shared stylesheet rather than adding an override layer.

New `resources/msoj-fonts.css` and five local WOFF2 subsets (Inter Latin/Latin Extended/Vietnamese and Doto Latin/Latin Extended). Font-display swap and fallback are provided. SIL OFL redistribution licenses are retained in `resources/fonts/inter-OFL.txt` and `resources/fonts/doto-OFL.txt`; sources: Google Fonts distribution at https://github.com/google/fonts/tree/main/ofl/inter and https://github.com/google/fonts/tree/main/ofl/doto.

## Executed Verification

- `sh make_style.sh`: successful light/dark builds, including the last modern-reader underline repair. Existing outdated Browserslist/caniuse-lite warning remains.
- `venv/bin/python manage.py check`: no issues (99 silenced).
- Actual Playwright through Chromium CDP, using isolated tooling under `/tmp/msoj-refresh-qa/`; no project dependency change.
- 13 matched routes × two themes × desktop 1365×900/mobile 390×844 = **52 baseline and 52 final screenshots**. All final states HTTP 200; content links/forms match baseline; no document overflow; zero captured JS page errors. Evidence: `baseline.json`, `final.json`.
- **44 WCAG-tagged axe states:** no detected violations after fixes. Additional expanded Roadmap states: four scans without violations. Additional modern reader final states: four scans without violations. These are automated checks, not WCAG certification.
- **120 responsive checks:** six key routes × two themes × 320/390/760/761/850/851/1000/1100/1101/1365px; no document overflow or navigation/account overlap. Evidence: `breakpoints.json`.
- Keyboard mobile menu: Space opens, `aria-expanded` updates; Escape closes and restores trigger focus. Settings popup keyboard access, Light/Auto submission and OS light/dark auto resolution exercised. Reduced-motion reports landing animation `none`. Skip link is first Tab stop; Enter focuses `#content`.
- Problems: search GET URL, matching result, no-match empty result, Select2 open/Escape; original query/forms retained.
- Roadmap: actual lazy branch request increases visible node inventory from 13 to 23; disclosure expansion/collapse exercised in both themes; expanded desktop/mobile screenshots retained.
- Workspace: ArrowRight changes resize value to 55; collapse/restoration exercised; statement keyboard scrolling and five real MathJax expressions observed. Four theme/viewport math states have zero TeX error elements.
- Actual Ace engine browser-only smoke: keyboard input preserved expected source in four theme/viewport states; text stays Liberation Mono/monospace and contained. Probe removed. This is not authenticated submission-form verification.
- Cache cutover: explicit/auto themed asset URLs observed with no static HTTP errors; extra `/posts/`, `/runtimes/matrix/`, `/organizations/` runtime navigation checked.
- No permanent tests added or test suite run: this is visual presentation work; verification was rendered/browser smoke plus existing build and Django system check.

## Screenshots and Evidence

Local evidence directory: `/tmp/msoj-visual-refresh/`.

- `before/{route}-{light|dark}-{desktop|mobile}.png`
- `after/{route}-{light|dark}-{desktop|mobile}.png`
- Routes: landing, problems, roadmap, workspace, submissions, contests, users, blogs, reader, status, login, about, runtimes.
- Four comparison sheets: `comparison-light-desktop.png`, `comparison-dark-desktop.png`, `comparison-light-mobile.png`, `comparison-dark-mobile.png`. Each shows BEFORE/AFTER for six primary areas.
- Expanded map, editor engine smoke and modern-reader screenshots are separately named in `after/`.
- `modern-reader.json` preserves the earlier failing finding. `modern-reader-final.json` supersedes it after the underline repair; all four final states pass the exercised checks.
- JSON evidence: `axe-final.json`, `breakpoints.json`, `interactions.json`, `editor-smoke.json`, `final.json`, `theme-assets.json`, `modern-reader-final.json`.

These local screenshots are review artifacts, not production data and not Git-staged assets.

## Remaining Limits / Owner Review

- Empty original prompt prevents comparison against its missing motion/mobile details. Screenshot extraction and MSOJ adaptations are documented separately.
- Owner must judge whether the adapted cinematic intensity, Doto brand accent and pill navigation meet the desired visual direction. Engineering completion is not Visual Acceptance.
- Anonymous/local dataset only: authenticated submission, AI workflows, permissions variants, organization-specific content, populated contests and multi-page pagination were not exercised. Their backend/form/route contracts were not intentionally changed; parity evidence covers rendered anonymous links/forms, not every conditional branch.
- Ace smoke used the real editor engine in a temporary browser node; authenticated application editor/form flow remains unverified.
- Actual screen-reader speech, all browser engines, production compression/deployment/static collection and low-end-device performance profiling were not tested.
- Modern reader has final screenshots but no newly claimed before capture; the matched 52-state baseline includes the classic reader. No baseline was fabricated after implementation.
- Temporary QA packages and evidence remain under `/tmp`; browser-only probes were removed. No production/runtime directory was modified.

## Navigation Refinement — Home Floating / Functional Docked

Implemented the approved text-wireframe direction. Home retains its existing capsule geometry and landing offsets. All other `base.html` pages default to a fixed full-width 56px navigation: no outer radius/shadow, thin bottom border. Menu, active pills, typography, themes and behavior remain shared.

- `templates/base.html` / `templates/landing.html`: explicit shell/navigation variant blocks; shared cache version `visual-refresh-2`.
- `resources/navbar.scss`: docked default, landing-only capsule, aligned container/account gutters, desktop dropdowns below 56px bar, existing mobile drawer beneath its variant. Workspace nav uses its wide gutter.
- `resources/base.scss`: 56px shell token; desktop content begins at 80px (24px after nav), mobile retains its content padding. Docked-only removal of obsolete shell `<br>` spacing. Repaired reduced-motion specificity after observing the ineffective old cascade.
- `resources/problem-workspace.css`: content/sticky context at 56px; removed trailing mobile 54px override overlapping nav by 2px on scroll. Pane-sizing JS unchanged; CSS cache version 21.

Verification for this refinement:

- `sh make_style.sh`: light/dark builds passed after final refinement; existing outdated Browserslist warning remains. `venv/bin/python manage.py check`: no issues, 99 silenced.
- Playwright/Chromium: 32 matched before/after states on Home, Problems, Workspace, Roadmap, Submissions, Contests, Blogs and modern Reader; light/dark × desktop 1365×900 / mobile 390×844. HTTP 200 throughout; zero document overflow, detected WCAG-tagged axe violations or captured page errors. Home geometry and content link/form contracts unchanged in every matched state.
- Final responsive matrix: 48 checks on Home/Problems/Workspace, both themes, widths 320/760/761/850/851/1100/1101/1568; zero document overflow, visible-menu/account overlap or initial nav/context overlap.
- Keyboard: Space opens mobile menu; Escape closes/restores trigger focus on Home/Problems. Settings popup opens by focus. Desktop About dropdown begins at 56px. Skip link is first Tab stop; Enter focuses content.
- Workspace: keyboard separator resize to 55%; editor pane collapse/restore. Desktop context top equals nav bottom (56px); workspace bottom equals 900px viewport. Scrolled mobile context settles at 56px in both themes. Five MathJax expressions, zero TeX errors in all four states.
- Real Ace engine in a temporary browser-only node: keyboard input produced `int main() { return 0; }` in four theme/viewport states; probe removed. Initial multiline expectation was corrected because Ace legitimately auto-indents later lines. Authenticated application submission remains unverified.
- Auto resolves white/charcoal nav under OS light/dark. Final uncached reduced-motion verification reports `0s` nav transition on Home/Problems in both OS schemes.

Evidence: `/tmp/msoj-nav-variants/` contains `baseline.json`, `matrix.json`, `breakpoints.json`, `interactions.json`, `final-smoke.json`, `before/`, `after/` and four `comparison-{light,dark}-{desktop,mobile}.png` sheets. Light Problems desktop/mobile and dark Workspace desktop screenshots visually inspected. Browser released; no permanent tests or backend behavior changes. No commit/deploy/migration/production-data change. Owner Visual Acceptance remains unclaimed.

## Navigation Consistency Correction

User screenshots exposed inconsistent desktop alignment: Problems and other functional pages capped `#nav-container` at 1440px, while a Workspace-only override expanded it. Corrected `resources/navbar.scss` by making that full-width container/gutter rule apply to every `.ms-nav-docked` navigation and removing the obsolete separate account-padding rule. Mobile uses the same 6px container padding and 10px account inset across functional pages. Home floating rules and all content-layout styles unchanged. Shared CSS cache version advanced to `visual-refresh-3`; light/dark styles rebuilt successfully (existing Browserslist warning).

Final Playwright evidence: `/tmp/msoj-nav-consistency/final.json` contains 72 settled states: Home, Problems, Workspace, Roadmap, Submissions and Contests × light/dark × 320/390/1100/1101/1568/2352px. Zero overflow or menu/account overlap. Functional nav/container/menu/account rectangles match Workspace exactly at each theme/width. 36 WCAG-tagged axe scans report zero detected violations. Home outer navigation/container geometry unchanged against captured baseline. Content position/width unchanged; Submissions content height differed by 3px between captures, so full content-rectangle equality is not claimed. No content styling was edited.

Keyboard evidence in `interactions.json`: Problems/Workspace mobile Space opens menu, Escape closes and restores trigger focus; desktop dropdown is visible by focus and starts at 56px. Screenshots in `before/` and `after/` include 1568px and 2352px desktop and 390px mobile; Problems/Workspace ultrawide light screenshots visually inspected. Broader preliminary route scans were interrupted; only completed settled states above count as final evidence. Anonymous local QA, not the user's authenticated admin session. No commit, deployment, migration or database changes. Home remains untouched; owner Visual Acceptance not claimed.

## Roadmap — Goal-Based Staged Explorer

Replaced the recursive learner map with two complementary modes: **Đường tới mục tiêu** derives prerequisite closure and topological stages; **Danh mục chuyên đề** retains taxonomy lookup without presenting groups as numbered learning steps. The published canonical PUBLIC curriculum uses approved `curriculum_v1.json` prerequisite metadata; other roadmaps use existing database edges. No seeding, migration or application-data mutation was performed for this cutover.

- `mentor/roadmap_explorer.py`: authorized effective-published nodes serialized in one batch; prerequisite/successor graphs; goal selection; stage bounds; selection URLs that follow the relation's actual stage; explicit incomplete-path state for missing dependencies/cycles. Hidden endpoints and their dependency reasons never render. Canonical manifest errors propagate rather than silently inventing a path.
- `mentor/roadmap_pages.py`: HTML adapter integration; existing JSON APIs, learning routes, focus links, privacy headers and AC semantics retained. AC remains practice evidence, not mastery or an unlocking gate.
- `templates/roadmap/map.html`, `nodes.html`, `resources/roadmap.js`: single clickable node surface, searchable existing Select2 goal picker with explicit submit, free stage navigation, contextual sidebar/mobile sheet, real readiness-gated learning CTA, SSR links/forms. Removed obsolete recursive expansion. Fresh authorized HTML enhancement uses cancellation plus controller identity checks, URL-only history, error/retry, modified-click preservation, modal inert background and focus restoration. Script cache `staged-roadmap-1`; shared CSS cache `visual-refresh-4`.
- `resources/roadmap.scss`: scoped shared-token surfaces and pills, theme-safe badges, responsive card grid, viewport-bottom mobile sheet, reduced-motion handling; existing learning prose styles retained. Visual QA found and corrected active-pill count opacity contrast, inherited desktop `top` on mobile sheet, and an empty child-group strip.

Verification:

- `sh make_style.sh`: final light/dark builds passed; existing outdated Browserslist warning remains. `node --check resources/roadmap.js` passed.
- Isolated Django runner: 62 tests passed across roadmap, explorer, pages, API, learning, curriculum and migration test modules; final seven page tests passed after the last template/assertion refinement. Migrations/seed commands executed only against disposable test databases. Django test system checks report no issues, 99 silenced.
- Playwright/Chromium final matrix: 18 settled states, light/dark × 1365×900 / 390×844 / 320×760 × path / selected DFS / nested catalog. HTTP 200, zero document overflow, zero captured page errors and zero detected WCAG-tagged axe violations in the Roadmap surface. Final mobile panels end at the viewport bottom and isolate navigation with `inert`.
- Exercised next stage, direct node selection, recursion→DFS relation across stages, browser Back with null history state, searchable Lazy Propagation goal with explicit submit, Tab/Shift+Tab trap, Escape, relation and direct-URL close focus restoration, desktop resize modal teardown, aborted-network retry with correct URL, and latest-request-wins. No-JS GET form, selection and taxonomy drilldown work. Auto theme resolves light/dark surfaces; reduced-motion transitions/animations report `0s`.

Evidence: `/tmp/msoj-roadmap-staged/index.html` pairs four light/dark desktop/mobile before/after captures; `after/` also includes selected-node and catalog screenshots. `matrix.json`, `interactions.json`, `fallbacks.json`, `http-contracts.json` and `summary.json` contain exercised results. Final light desktop, dark mobile selected and nested catalog screenshots visually inspected.

Limit: the local published curriculum has no available `learn_url`; the browser correctly shows **Sắp cập nhật** and no fake learning CTA. Readiness/real learning URL behavior is covered by backend fixtures, not a newly populated browser learning path. Authenticated AC display, screen-reader speech and other browser engines are not newly claimed. No commit, deployment, production-data change or owner Visual Acceptance.

## Roadmap — Goal-First Layout Refinement

- Replaced stage-by-stage navigation with the complete prerequisite path on one page: goal heading, numbered preparation layers, then node details only on selection. DFS renders five topics across three layers; Lazy Propagation renders six topics across four layers. Layer order is guidance, not an all-to-all dependency claim or learning gate.
- Removed redundant stage controls, badges, introductory chrome and the empty detail surface. Catalog renders taxonomy groups directly; nested groups retain breadcrumbs and authorized links. Goal search remains an explicit-submit GET form enhanced by existing Select2.
- Reused shared surface, typography, border, focus, radius and motion tokens. Retained learning-page styles; no backend, judge, AI, permission, route or curriculum-data changes in this refinement. CSS cache is `visual-refresh-5`; Roadmap script cache is `goal-first-3`.
- Corrected inherited disclosure boxes, positioned the goal dropdown within its form, labeled the enhanced picker/search and supplied expanded combobox controls. Mobile Tab trapping includes summary elements but excludes collapsed disclosure content.

Verification:

- Light/dark SCSS builds passed; existing outdated Browserslist warning remains. Final `node --check resources/roadmap.js` passed.
- Playwright/Chromium: 24 states across light/dark, 1365/390/320px, path/selected DFS/root catalog/nested catalog. All HTTP 200; no document overflow, captured page errors or WCAG-tagged axe findings in the Roadmap surface. Twelve additional open/closed goal-picker scans passed after fixing the two expanded-state ARIA findings.
- Exercised goal search and explicit submission, settled keyboard goal selection, mobile relation navigation, collapsed/expanded disclosure Tab boundaries, Escape, history Back, no-JS goal form/details/catalog drilldown, network retry, latest-request-wins, auto light/dark, reduced-motion zero transitions, mobile-to-desktop dialog teardown and direct-URL close focus restoration.
- DFS first card is at y=405px on desktop and y=459px at 390px width. Selected mobile sheet ends at viewport bottom; desktop resize removes dialog role and background inert state.

Evidence: `/tmp/msoj-roadmap-redesign/index.html` pairs previous-stage and final goal-first light/dark desktop/mobile screenshots. `after/` includes selected-node, catalog and larger-goal captures; `matrix.json`, `interactions.json` and `picker.json` contain observed results.

Limits: anonymous Chromium session; real screen-reader speech and other browser engines not tested. Local curriculum has no available learning URLs; readiness remains covered by the earlier backend fixtures, not newly populated browser content. Backend tests were not rerun for this template/style/interaction-only refinement. No commit, deployment, production-data change or owner Visual Acceptance.

## Roadmap — Macro Learning Journey

- Replaced the canonical root catalog's flat grid with four connected learning milestones: foundations; core tools (basic algorithms/data structures/math); solving directions (DP/graphs/trees/strings); specialized branches (geometry/flow/games/advanced search). Contest skills remain parallel practice rather than a final gate.
- Milestones are presentation guidance, not prerequisite edges, learner completion or unlock rules. Group cards retain original authorized URLs and use approved learner-safe manifest introductions. Only effectively published root groups enter the journey; noncanonical roadmaps retain their ordinary catalog and additional canonical roots are not dropped.
- Group and nested-topic catalogs show the owning root group's milestone using `aria-current="location"`. Links return to the exact milestone with focus and scroll restoration after authorized HTML enhancement; native anchors also work without JavaScript. Goal-specific prerequisite paths and detail sheets remain intact.
- Shared path/card/token primitives reused; CSS cache `visual-refresh-6`, Roadmap script `macro-journey-1`. No curriculum seed, database write, migration, Judge or AI workflow change.

Verification: light/dark SCSS builds and JavaScript syntax passed (existing Browserslist warning remains). `RoadmapJourneyTests` passed without database setup; regression covers supplied-root boundaries, nested-group orientation, additional groups and noncanonical exclusion. Playwright/Chromium: 24 root/group/nested/goal states at 1365/390/320px across light/dark, all HTTP 200, no horizontal overflow, page errors or detected WCAG-tagged axe findings in the Roadmap surface. Root journey contains all 13 public groups across four milestones plus parallel practice. Keyboard milestone return focuses its anchor at y=80px; Back returns to the group. No-JS drilldown/anchor, goal detail/Escape, auto theme and reduced-motion zero transitions exercised.

Evidence: `/tmp/msoj-roadmap-macro/index.html` pairs before/after light/dark desktop/mobile; `matrix.json`, `interactions.json`, `themes.json` record observed results. Root dark desktop and nested light mobile visually inspected.

Limits: macro grouping is a proposed instructional overview, not a strict learning dependency graph. Anonymous Chromium only; no real screen-reader speech test or owner Visual Acceptance. No commit, deployment or production-data change.

## Roadmap — Searchable Topic Finder

- Replaced the enhanced nested Select2 goal dropdown with a scoped native modal dialog: direct search, root-group browse/filter, explicit topic links and empty-result recovery. Desktop uses a wider panel; mobile uses the viewport with a scrolling result body. The original GET select/form remains the no-JS/unsupported-dialog fallback and no longer initializes Select2.
- Searches normalize Vietnamese accents and đ, English names, whitespace/case; explicit canonical aliases support DFS/BFS expanded names, DP/qhd, cây đoạn/segtree, BIT/Fenwick, tknp and lazy. Exact title/alias/parenthetical matches rank before prefix and partial matches. No AI, fuzzy guessing or private provider data.
- Results show authorized ancestor paths, difficulty and real lesson readiness. Group filter is visible and removable without clearing the search. Supplied published nodes alone populate results; aliases are canonical-curriculum-only. Native modal Escape/inert behavior, explicit Tab wrap, arrow movement through links and opener focus restoration included. Typing/arrows do not navigate; Enter on a result or click chooses its goal.
- Reused shared tokens/card grid/pill actions. Finder group buttons are excluded from the legacy shared pill selector so long names wrap in neutral surfaces rather than clipping. Removed obsolete goal Select2 init/destroy and AJAX form code. CSS cache `visual-refresh-7`, script `topic-finder-1`.

Verification: light/dark builds and final JavaScript syntax passed; existing Browserslist warning remains. Two focused no-database regressions passed for macro journey and finder ancestor/alias boundaries. Final Playwright/Chromium matrix: 18 light/dark × 1365/390/320px × groups/search/empty dialog states, no document/dialog overflow, page errors or detected WCAG-tagged axe findings. Final computed group labels wrap normally; desktop group and dark mobile result screenshots visually inspected. Ten observed query cases rank the intended topic first, including DFS, depth first search, qhd, dp, accented/unaccented quy hoạch động, segment tree, cây đoạn, binary search and BIT. Keyboard selection opens DFS only on Enter with heading focus; wrong-group empty state recovers on All groups. Tab/Shift+Tab wrap and Escape return focus; no-JS form opens Lazy Propagation. Auto theme resolves both surfaces and reduced-motion reports zero transition.

Evidence: `/tmp/msoj-roadmap-finder/index.html`, `after/`, `matrix.json`, `searches.json`, `interactions.json`, `themes.json`. Limits: explicit aliases are curated, not arbitrary synonym/typo understanding; anonymous Chromium, no actual screen-reader speech or owner Visual Acceptance. No commit, deployment, migration or production-data change.

## Roadmap — Native Lectures, Phase 1

- Reused `RoadmapNode -> LearningTopic -> TopicLesson`, not a second lecture system. Added authored Markdown summary with the existing publication/admin preview controls. A topic can be reused in multiple nodes; lesson order and each node's own practice remain intact.
- Lesson page has reading, summary and an explicitly labelled **native MSOJ slide placeholder**. No slide editor, graph/geometry visualizer, PDF slide conversion, video or voice implementation is implied. Desktop tutor sits beside reading; mobile switches to a separate AI panel without losing reading scroll or the current question. Heading directory, keyboard tabs, MathJax and no-JavaScript content remain usable.
- `TopicLessonState` stores user/lesson reading offset (0..10000), content revision and monotonic position version. Keepalive lifecycle flushes can overlap a pending save; the server ignores older/equal versions so delayed requests cannot overwrite the newest position. Published accessible prior lessons receive an overview resume link; changed content resets stable offset. Reading never writes mastery or AC state.
- `lecture_services.py` uses only authorized published lesson body/summary and optional verified section, with separate server-only instructions and structured lower-trust data. Generator and reviewer share the same bounded canonical context; overlong context fails explicitly, not silently truncated. Only approved pairs enter private user/lesson/revision history; responses are escaped/plain text. Access, attachment and revision are checked before each provider call and publication. Active non-spectator contest participation disables tutor Q&A.
- POST-only lesson `questions/` and `state/` endpoints require authenticated writes and CSRF; private/no-store responses contain safe codes only. Durable per-user reservations prevent concurrent paid turns; all attempts count toward 5/minute and 20 per lesson revision, including rejected/failed calls. Provider details, prompts, drafts and reviewer reasons remain server-side.

Verification: light/dark SCSS build and JS syntax passed (existing outdated Browserslist warning). Django check found no issues (99 existing silenced); migration-state check found no pending model changes. 26 focused tests in `mentor.tests_roadmap_learning` and `mentor.tests_lecture` passed on an isolated MariaDB test database, including out-of-order final-position writes. Another 23 existing roadmap API/page/admin integration tests passed. Disposable HTTP/CSRF smoke with controlled Gateway results observed approved 200, rejected 422, and no unapproved draft persistence. No real provider completion was called.

Playwright/Chromium: 22 light/dark reading/summary/slide/tutor states at 1365/390/320px; no horizontal overflow, page errors or detected WCAG-tagged axe violations in the lecture surface. Saved 5500/10000 reading offset and restored it after reload, including a save while reading panel was hidden. Mobile reading scroll stayed 700px across tutor switching and unsent question stayed intact. Arrow-key tabs, heading-link focus, overview resume, offline recovery, unconfigured-AI recovery, no-JS reading/summary and actual MathJax rendering exercised. Auto dark and reduced-motion zero control transitions confirmed. Visually inspected desktop reading and mobile tutor/slide placeholder.
Final lifecycle race smoke held a pending 3000/10000 save, dispatched a newer 8000/10000 pagehide keepalive, then released the older request. Reload restored 8001/10000 (scroll rounding), proving the older request did not overwrite the final position. Independent scoped review found this resume race; it was fixed and covered by the permanent ordering regression and browser smoke. No other blocking review finding was reported.

Evidence: `/tmp/msoj-lecture/index.html`, `browser.json`, `interactions.json`, `save-race.json`, `before/`, `after/`. Before images are the prior verified learning-page fixture, not a same-content pixel diff. No real screen-reader speech or owner Visual Acceptance.

Activation: new `mentor/migrations/0009_lecture_content_state_qa.py` is supplied but **not applied to the existing runtime/production database**. Configure enabled AI Gateway routes `lesson_tutor_generate` and `lesson_tutor_review` with existing server-side connections/credentials before live Q&A. Migration must precede serving the changed lesson pages. No lecture curriculum content was seeded into existing runtime data.

Operational limits: two synchronous Gateway calls per question; no added retry loop or streaming of unreviewed text. Canonical context cap 16000 characters; question cap 2000; approved answer cap 4000. A process crash can leave an ACTIVE reservation: fail closed rather than silently duplicate paid work. An operator must confirm the original request worker has stopped, then mark that specific attempt failed with a completion timestamp before the user can ask again. Private history remains revision-scoped. Video, voice, native slide authoring and interactive visualizers remain the explicitly requested Phase 2 scope.

