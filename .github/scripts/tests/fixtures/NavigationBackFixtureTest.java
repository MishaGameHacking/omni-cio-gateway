package ru.omnicio.ciframe;

/** Exercise the actual admission class; no emulator evidence is manufactured. */
public final class NavigationBackFixtureTest {
    private static int cases;

    private static String root(String route, String scenario) {
        return "probe-screen:automation-" + route + ";probe-scenario:" + scenario + ";probe-run:synthetic-test";
    }

    private static String trace(String route, String scenario, String transport, String page) {
        return "automation-probe:" + route + "/" + scenario + ";transport:" + transport
                + ";page:" + page + ";requests:1;contract-errors:0";
    }

    private static NavigationBackFixture gate(String root, String trace, boolean panel, boolean close) {
        NavigationBackFixture value = new NavigationBackFixture();
        value.observeDescription(root);
        value.observeDescription(trace);
        if (panel) value.observeVisibleResource("navigation-panel");
        if (close) value.observeVisibleResource("navigation-menu-close");
        return value;
    }

    private static void expect(NavigationBackFixture value, boolean expected) {
        cases++;
        if (value.allowed() != expected) throw new AssertionError("navigation admission case " + cases);
    }

    public static void main(String[] args) {
        for (String route : new String[] {"home", "settings"}) {
            for (String page : new String[] {"home", "decisions", "settings"}) {
                expect(gate(root(route, "ready"), trace(route, "ready", "synthetic", page), true, true), true);
            }
            for (String scenario : new String[] {"error", "paused", "not_connected", "conflict", "live"}) {
                expect(gate(root(route, scenario), trace(route, scenario, "synthetic", route), true, true), false);
            }
        }
        expect(gate(root("home", "ready"), trace("settings", "ready", "synthetic", "settings"), true, true), false);
        expect(gate(root("decisions", "ready"), trace("decisions", "ready", "synthetic", "decisions"), true, true), false);
        expect(gate(root("home", "ready"), trace("home", "ready", "network", "home"), true, true), false);
        expect(gate(root("home", "ready"), trace("home", "ready", "synthetic", "unknown"), true, true), false);
        expect(gate(root("home", "ready"), trace("home", "ready", "synthetic", "home"), false, true), false);
        expect(gate(root("home", "ready"), trace("home", "ready", "synthetic", "home"), true, false), false);
        expect(gate(null, trace("home", "ready", "synthetic", "home"), true, true), false);
        expect(gate(root("home", "ready"), null, true, true), false);
        expect(gate(root("home", "ready") + ";probe-scenario:ready",
                trace("home", "ready", "synthetic", "home"), true, true), false);
        for (String changed : new String[] {"requests:0", "requests:1.0", "requests:1000000000000"}) {
            expect(gate(root("home", "ready"), trace("home", "ready", "synthetic", "home")
                    .replace("requests:1", changed), true, true), false);
        }
        expect(gate(root("home", "ready"), trace("home", "ready", "synthetic", "home")
                .replace("contract-errors:0", "contract-errors:1"), true, true), false);
        NavigationBackFixture duplicate = gate(root("home", "ready"), trace("home", "ready", "synthetic", "home"), true, true);
        duplicate.observeDescription(root("home", "ready"));
        duplicate.observeDescription(trace("home", "ready", "synthetic", "home"));
        expect(duplicate, true);
        duplicate.observeDescription(root("settings", "ready"));
        expect(duplicate, false);
        NavigationBackFixture conflict = gate(root("settings", "ready"), trace("settings", "ready", "synthetic", "settings"), true, true);
        conflict.observeDescription(trace("home", "ready", "synthetic", "home"));
        expect(conflict, false);
        NavigationBackFixture unrelated = gate(root("home", "ready"), trace("home", "ready", "synthetic", "home"), false, false);
        unrelated.observeVisibleResource("not-navigation-panel");
        unrelated.observeVisibleResource("navigation-menu-close-extra");
        expect(unrelated, false);
        System.out.println("NAVIGATION_BACK_FIXTURE_CASES=" + cases);
    }
}
