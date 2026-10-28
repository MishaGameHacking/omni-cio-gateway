package ru.omnicio.ciframe;

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
