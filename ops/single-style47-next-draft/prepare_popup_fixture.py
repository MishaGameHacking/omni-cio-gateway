"""Prepare strict native admission for the production dock over its debug host."""

JAVA = r'''package ru.omnicio.ciframe;

import java.util.HashMap;
import java.util.Map;

/** Test-only admission: one current popup and one matching synthetic host window. */
final class DockBackFixture {
    private final int popup;
    private final Map<Integer, Host> hosts = new HashMap<>();
    private boolean panel, close, content, invalid;

    private static final class Host {
        boolean screen, trace;
        String run, user;
    }

    DockBackFixture(int popup) { this.popup = popup; }

    void observeDescription(int window, CharSequence description) {
        if (description == null) return;
        String raw = description.toString();
        if (!raw.contains("probe-screen:") && !raw.contains("navigation-detail:")) return;
        if (window == popup) { invalid = true; return; }
        Map<String, String> fields = new HashMap<>();
        for (String part : raw.split(";")) {
            int colon = part.indexOf(':');
            if (colon < 0) continue;
            if (fields.put(part.substring(0, colon), part.substring(colon + 1)) != null) {
                invalid = true; return;
            }
        }
        Host host = hosts.computeIfAbsent(window, ignored -> new Host());
        if (fields.containsKey("probe-screen")) {
            String run = fields.get("probe-run");
            if (!"business-strategy".equals(fields.get("probe-screen"))
                    || !"ready".equals(fields.get("probe-scenario"))
                    || run == null || !run.matches("[A-Za-z0-9_-]{1,128}")
                    || (host.run != null && !host.run.equals(run))) invalid = true;
            else { host.screen = true; host.run = run; }
        }
        if (fields.containsKey("navigation-detail")) {
            String requests = fields.get("requests"), user = fields.get("user");
            if (!"business-strategy/ready".equals(fields.get("navigation-detail"))
                    || !"synthetic".equals(fields.get("transport"))
                    || !"strategy".equals(fields.get("page"))
                    || !"0".equals(fields.get("writes"))
                    || !"0".equals(fields.get("contract-errors"))
                    || requests == null || !requests.matches("[1-9][0-9]{0,11}")
                    || user == null || !user.matches("synthetic-business-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
                    || (host.user != null && !host.user.equals(user))) invalid = true;
            else { host.trace = true; host.user = user; }
        }
    }

    void observeVisibleResource(int window, String resource) {
        if (window != popup) return;
        if ("navigation-panel".equals(resource)) panel = true;
        if ("navigation-menu-close".equals(resource)) close = true;
        if ("navigation-panel-content".equals(resource)) content = true;
    }

    boolean allowed() {
        if (invalid || !panel || !close || !content || hosts.size() != 1) return false;
        Host host = hosts.values().iterator().next();
        return host.screen && host.trace && host.run != null && host.user != null;
    }
}
'''

TEST = r'''package ru.omnicio.ciframe;

/** Real admission implementation; synthetic values do not claim native UI success. */
public final class DockBackFixtureTest {
    private static int cases;
    private static final String SCREEN = "probe-screen:business-strategy;probe-scenario:ready;probe-run:real-run-123";
    private static final String TRACE = "navigation-detail:business-strategy/ready;transport:synthetic;page:strategy;requests:2;writes:0;contract-errors:0;user:synthetic-business-00000000-0000-4000-8000-000000000001";
    private static DockBackFixture fixture(String screen, String trace, int screenWindow, int traceWindow) {
        DockBackFixture gate = new DockBackFixture(12);
        gate.observeDescription(screenWindow, screen);
        gate.observeDescription(traceWindow, trace);
        for (String id : new String[] {"navigation-panel", "navigation-menu-close", "navigation-panel-content"})
            gate.observeVisibleResource(12, id);
        return gate;
    }
    private static void expect(DockBackFixture gate, boolean value) {
        cases++;
        if (gate.allowed() != value) throw new AssertionError("dock admission case " + cases);
    }
    public static void main(String[] args) {
        expect(fixture(SCREEN, TRACE, 10, 10), true);
        expect(fixture(SCREEN, TRACE, 10, 11), false);
        expect(fixture(SCREEN, TRACE, 12, 12), false);
        expect(fixture(null, TRACE, 10, 10), false);
        expect(fixture(SCREEN, null, 10, 10), false);
        for (String wrong : new String[] {"transport:network", "writes:1", "contract-errors:1",
                "requests:0", "requests:2.0", "page:appearance", "user:real-owner"}) {
            String key = wrong.substring(0, wrong.indexOf(':') + 1);
            expect(fixture(SCREEN, TRACE.replaceAll(key + "[^;]+", wrong), 10, 10), false);
        }
        expect(fixture(SCREEN.replace("ready", "error"), TRACE, 10, 10), false);
        expect(fixture(SCREEN.replace("business-strategy", "automation-home"), TRACE, 10, 10), false);
        expect(fixture(SCREEN + ";probe-run:other", TRACE, 10, 10), false);
        DockBackFixture duplicate = fixture(SCREEN, TRACE, 10, 10);
        duplicate.observeDescription(10, SCREEN); duplicate.observeDescription(10, TRACE);
        expect(duplicate, true);
        duplicate.observeDescription(11, SCREEN); duplicate.observeDescription(11, TRACE);
        expect(duplicate, false);
        DockBackFixture replaced = fixture(SCREEN, TRACE, 10, 10);
        replaced.observeDescription(10, SCREEN.replace("real-run-123", "another-run"));
        expect(replaced, false);
        for (String missing : new String[] {"navigation-panel", "navigation-menu-close", "navigation-panel-content"}) {
            DockBackFixture gate = new DockBackFixture(12);
            gate.observeDescription(10, SCREEN); gate.observeDescription(10, TRACE);
            for (String id : new String[] {"navigation-panel", "navigation-menu-close", "navigation-panel-content"})
                gate.observeVisibleResource(id.equals(missing) ? 10 : 12, id);
            expect(gate, false);
        }
        expect(fixture("probe-screen:business-strategy;probe-scenario:ready", TRACE, 10, 10), false);
        System.out.println("DOCK_BACK_FIXTURE_CASES=" + cases);
    }
}
'''


def apply(files, base):
    root = 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/'
    files[root + 'DockBackFixture.java'] = JAVA
    path = root + 'BackGestureInput.java'
    value = files[path] if path in files else base(path)
    old = 'if (!hasSpatialMarker(root, 0, new int[] {0}) && !hasAutomationNavigationMenu(root)) {'
    new = 'if (!hasSpatialMarker(root, 0, new int[] {0}) && !hasAutomationNavigationMenu(root)\n                && !hasOwnedDock(root)) {'
    assert value.count(old) == 1
    value = value.replace(old, new)
    anchor = '    private static boolean hasSpatialMarker('
    addition = '''    private boolean hasOwnedDock(AccessibilityNodeInfo root) throws IOException {
        DockBackFixture gate = new DockBackFixture(root.getWindowId());
        Rect display = windows.getMaximumWindowMetrics().getBounds();
        java.util.List<AccessibilityWindowInfo> observed = automation.getWindows();
        if (observed == null || observed.size() > 32) return false;
        boolean popupPresent = false;
        for (AccessibilityWindowInfo window : observed) {
            if (window.getType() != AccessibilityWindowInfo.TYPE_APPLICATION
                    || window.getDisplayId() != android.view.Display.DEFAULT_DISPLAY) continue;
            AccessibilityNodeInfo owner = window.getRoot();
            if (owner == null || !APP_PACKAGE.contentEquals(owner.getPackageName())) continue;
            if (window.getId() == root.getWindowId()) {
                if (!window.isActive() || !window.isFocused()) return false;
                popupPresent = true;
            } else if (window.isActive() || window.isFocused()) return false;
            observeDock(owner, gate, window.getId(), display, 0, new int[] {0});
        }
        return popupPresent && gate.allowed();
    }

    private static void observeDock(AccessibilityNodeInfo node, DockBackFixture gate,
            int window, Rect display, int depth, int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) throw new IOException("Dock fixture exceeds node budget");
        if (!APP_PACKAGE.contentEquals(node.getPackageName())) return;
        gate.observeDescription(window, node.getContentDescription());
        if (node.isVisibleToUser() && node.isEnabled()) {
            Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
            if (bounds.intersect(display) && !bounds.isEmpty()) {
                String resource = node.getViewIdResourceName(), prefix = APP_PACKAGE + ":id/";
                if (resource != null && resource.startsWith(prefix)) resource = resource.substring(prefix.length());
                gate.observeVisibleResource(window, resource);
            }
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) observeDock(child, gate, window, display, depth + 1, count);
        }
    }

'''
    assert value.count(anchor) == 1
    files[path] = value.replace(anchor, addition + anchor)
    files['.github/scripts/tests/fixtures/DockBackFixtureTest.java'] = TEST
    path = '.github/scripts/tests/test_predictive_back_input.py'
    value = files[path] if path in files else base(path)
    anchor = 'class JavaBackSequenceTests(unittest.TestCase):\n'
    addition = '''    def test_popup_admission_binds_current_menu_to_one_matching_synthetic_host(self):
        javac, java = shutil.which("javac"), shutil.which("java")
        if javac is None or java is None:
            self.skipTest("JDK required for the host popup admission regression")
        source = ROOT / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/DockBackFixture.java"
        harness = Path(__file__).parent / "fixtures/DockBackFixtureTest.java"
        with tempfile.TemporaryDirectory() as output:
            built = subprocess.run([javac, "--release", "17", "-d", output, str(source), str(harness)],
                                   capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([java, "-cp", output, "ru.omnicio.ciframe.DockBackFixtureTest"],
                                    capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("DOCK_BACK_FIXTURE_CASES=22", result.stdout)

'''
    assert value.count(anchor) == 1
    files[path] = value.replace(anchor, anchor + addition)
