package ru.omnicio.ciframe;

import java.util.HashMap;
import java.util.Map;

/** Admission for two ready, synthetic navigation fixtures; no Android operations. */
final class NavigationBackFixture {
    private String screen;
    private String trace;
    private boolean panel;
    private boolean close;
    private boolean invalid;

    void observeDescription(CharSequence description) {
        if (description == null) return;
        String raw = description.toString();
        if (!raw.contains("probe-screen:") && !raw.contains("automation-probe:")) return;
        Map<String, String> fields = new HashMap<>();
        for (String part : raw.split(";")) {
            int colon = part.indexOf(':');
            if (colon < 0) continue;
            if (fields.put(part.substring(0, colon), part.substring(colon + 1)) != null) {
                invalid = true;
                return;
            }
        }
        if (fields.containsKey("probe-screen")) {
            String candidate = switch (fields.get("probe-screen")) {
                case "automation-home" -> "home";
                case "automation-settings" -> "settings";
                default -> null;
            };
            if (candidate == null || !"ready".equals(fields.get("probe-scenario"))
                    || (screen != null && !screen.equals(candidate))) invalid = true;
            else screen = candidate;
        }
        if (fields.containsKey("automation-probe")) {
            String candidate = switch (fields.get("automation-probe")) {
                case "home/ready" -> "home";
                case "settings/ready" -> "settings";
                default -> null;
            };
            String page = fields.get("page");
            String requests = fields.get("requests");
            if (candidate == null || !"synthetic".equals(fields.get("transport"))
                    || !"0".equals(fields.get("contract-errors"))
                    || requests == null || !requests.matches("[1-9][0-9]{0,11}")
                    || !("home".equals(page) || "settings".equals(page) || "decisions".equals(page))
                    || (trace != null && !trace.equals(candidate))) invalid = true;
            else trace = candidate;
        }
    }

    void observeVisibleResource(String resource) {
        if ("navigation-panel".equals(resource)) panel = true;
        if ("navigation-menu-close".equals(resource)) close = true;
    }

    boolean allowed() {
        return !invalid && screen != null && screen.equals(trace) && panel && close;
    }
}
