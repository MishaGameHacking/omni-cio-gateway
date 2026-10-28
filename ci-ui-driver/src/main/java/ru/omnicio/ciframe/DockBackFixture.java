package ru.omnicio.ciframe;

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
