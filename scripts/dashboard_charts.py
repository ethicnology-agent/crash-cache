"""Chart specifications for the supported Metabase dashboard API."""

TEAL = "#168B83"
BLUE = "#509EE3"
CORAL = "#E76F51"
PURPLE = "#8B6BB1"
AMBER = "#E9B44C"


def specifications(queries):
    sessions, activity, health, devices, errors, _duplicates = queries
    hourly_sessions = sessions.replace("('day'), ('week'), ('month')", "('hour')")
    hourly_activity = activity.replace("('day'), ('week'), ('month')", "('hour')")

    def wrap(query, select):
        return f"WITH source AS ({query}) {select}"

    def graph(dimension, metrics, colors, **extra):
        return {"graph.dimensions": [dimension], "graph.metrics": metrics,
                "graph.colors": colors, "graph.show_values": False,
                "graph.y_axis.auto_range": True, "graph.y_axis.min": 0,
                "graph.show_goal": False, **extra}

    # Count installation identity over the whole selected range, not summed DAU.
    installations = activity[:activity.index("SELECT period.grain")]
    installations += "SELECT count(DISTINCT installation) AS active_installations FROM activity"
    return [
        {"name": "Observed installations", "description": "Distinct installations with foreground activity in this date range; installations are not people.",
         "query": installations, "display": "scalar", "settings": {"scalar.field": "active_installations", "scalar.decimals": 0}, "layout": (0, 0, 8, 4)},
        {"name": "Sessions started", "description": "Recorded session starts in this date range, across the configured clients.",
         "query": wrap(sessions, "SELECT coalesce(sum(sessions_started), 0) AS sessions FROM source WHERE grain = 'day'"),
         "display": "scalar", "settings": {"scalar.field": "sessions", "scalar.decimals": 0}, "layout": (0, 8, 8, 4)},
        {"name": "Reported crashed sessions", "description": "Sessions explicitly classified crashed. Open or missing terminal sessions are not proof of health.",
         "query": wrap(health, "SELECT coalesce(sum(crashes), 0) AS crashed_sessions FROM source"),
         "display": "scalar", "settings": {"scalar.field": "crashed_sessions", "scalar.decimals": 0}, "layout": (0, 16, 8, 4)},
        {"name": "Activity through the day", "description": "Distinct installations observed per UTC hour. No observation does not establish that nobody played.",
         "query": hourly_activity, "display": "line",
         "settings": graph("period_start", ["observed_active_installations"], [TEAL], **{"graph.show_dots": True, "graph.x_axis.title_text": "UTC hour", "graph.y_axis.title_text": "Observed installations", "line.interpolate": "linear"}), "layout": (4, 0, 12, 7)},
        {"name": "Session starts through the day", "description": "Recorded session starts per UTC hour, including controlled laboratory sessions.",
         "query": hourly_sessions, "display": "bar",
         "settings": graph("period_start", ["sessions_started"], [BLUE], **{"graph.x_axis.title_text": "UTC hour", "graph.y_axis.title_text": "Sessions"}), "layout": (4, 12, 12, 7)},
        {"name": "Session outcomes by release", "description": "Recorded outcomes; open and abnormal sessions remain visible instead of being called healthy.",
         "query": wrap(health, "SELECT concat(regexp_replace(split_part(release, '+', 1), '^.*@', ''), ' / ', environment) AS build, sum(sessions - crashes - abnormal - unhandled - still_open) AS exited, sum(crashes) AS crashes, sum(abnormal) AS abnormal, sum(unhandled) AS unhandled, sum(still_open) AS still_open FROM source GROUP BY build ORDER BY build"),
         "display": "bar", "settings": graph("build", ["exited", "crashes", "abnormal", "unhandled", "still_open"], [TEAL, CORAL, AMBER, PURPLE, BLUE], **{"stackable.stack_type": "stacked", "graph.x_axis.title_text": "Release / environment", "graph.y_axis.title_text": "Sessions", "graph.label_value_formatting": "compact"}), "layout": (11, 0, 12, 8)},
        {"name": "Error reports by capture layer", "description": "Report volume, not an error rate. Controlled error storms intentionally affect these counts.",
         "query": wrap(errors, "SELECT coalesce(layer, 'Unclassified') AS layer, sum(error_events) AS reports FROM source GROUP BY layer ORDER BY reports DESC"),
         "display": "bar", "settings": graph("layer", ["reports"], [CORAL], **{"graph.show_values": True, "graph.x_axis.title_text": "Capture layer", "graph.y_axis.title_text": "Reports"}), "layout": (11, 12, 12, 8)},
        {"name": "Observed devices and systems", "description": "Installations per device, system and app version; one installation can appear under multiple versions. Only foreground activity observations contribute.",
         "query": wrap(devices, "SELECT concat(coalesce(device_model, 'Unknown device'), ' / ', coalesce(os, 'Unknown OS'), ' ', coalesce(os_version, '?'), ' / app ', coalesce(app_version, '?'), ' (', coalesce(app_build, '?'), ') / ', coalesce(runtime_platform, '?')) AS device, observed_installations FROM source ORDER BY observed_installations DESC"),
         "display": "row", "settings": graph("device", ["observed_installations"], [PURPLE], **{"graph.show_values": True}), "layout": (19, 0, 24, 7)},
    ]
