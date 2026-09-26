#!/usr/bin/env python3
"""Provision the maintained observability collection using Metabase 0.63.18 APIs."""

import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import uuid

MARKER = "Managed by crash-cache observability provisioning."
COLLECTION = "Crash-cache observability"
DASHBOARD = "Application health and installations"
CARD_NAMES = (
    "Session starts and installations",
    "Observed active installations",
    "Release health",
    "Platforms, systems and devices",
    "Errors by runtime and component",
    "Duplicate cross-layer captures",
)


class ProvisionError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProvisionError("Metabase redirected an authenticated request; configure the final URL")


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.session = None
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method, path, body=None):
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["X-Metabase-Session"] = self.session
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + "/api" + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120) as response:
                content = response.read()
                return json.loads(content) if content else None
        except urllib.error.HTTPError as error:
            # Request and response bodies can contain credentials or private SQL results.
            raise ProvisionError(f"Metabase {method} {path}: HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise ProvisionError(f"Metabase {method} {path}: connection failed") from None


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ProvisionError(f"Set {name} in the private environment")
    return value


def rows(result):
    return result["data"] if isinstance(result, dict) else result


def unique_managed(items, name, collection_id=None):
    matches = [item for item in items if item.get("name") == name
               and (collection_id is None or item.get("collection_id") == collection_id)]
    if len(matches) > 1:
        raise ProvisionError(f"Multiple objects named {name}; resolve ambiguity before provisioning")
    if matches and not (matches[0].get("description") or "").startswith(MARKER):
        raise ProvisionError(f"Unmanaged object named {name}; refusing to overwrite it")
    return matches[0] if matches else None


def load_queries():
    sql = (Path(__file__).resolve().parents[1] / "docs/sql/observability.sql").read_text()
    sql = re.sub(r"(?m)^--.*$", "", sql)
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    queries = [part for part in statements if part.startswith(("WITH ", "SELECT "))]
    if len(queries) != len(CARD_NAMES):
        raise ProvisionError("Dashboard SQL count differs from maintained question definitions")
    return [query.replace(":project_id", "{{project_id}}")
            .replace(":'from'", "{{from}}")
            .replace(":'until'", "{{until}}") for query in queries]


def template_tags(project_id, start, end):
    definitions = (("project_id", "Project", "number", project_id),
                   ("from", "From (inclusive)", "date", start),
                   ("until", "Until (exclusive)", "date", end))
    return {name: {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "crash-cache:" + name)),
                   "name": name, "display-name": label, "type": kind,
                   "required": True, "default": default}
            for name, label, kind, default in definitions}


def query_parameters(project_id, start, end):
    return [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "crash-cache:" + name)),
             "type": kind, "target": ["variable", ["template-tag", name]], "value": value}
            for name, kind, value in (("project_id", "number", project_id),
                                      ("from", "date/single", start),
                                      ("until", "date/single", end))]


def provision(api, project_id, start, end):
    email, password = required("METABASE_ADMIN_EMAIL"), required("METABASE_ADMIN_PASSWORD")
    properties = api.call("GET", "/session/properties")
    setup_token = properties.get("setup-token")
    if setup_token:
        auth = api.call("POST", "/setup", {
            "token": setup_token,
            "user": {"email": email, "password": password, "first_name": "Lab", "last_name": "Operator"},
            "prefs": {"site_name": "Crash-cache observability", "site_locale": "en", "allow_tracking": False},
        })
    else:
        auth = api.call("POST", "/session", {"username": email, "password": password})
    api.session = auth["id"]
    databases = rows(api.call("GET", "/database"))
    details = {"host": os.environ.get("METABASE_SOURCE_HOST", "postgres"),
               "port": int(os.environ.get("METABASE_SOURCE_PORT", "5432")),
               "dbname": "crash_cache", "user": "metabase_readonly",
               "password": required("METABASE_READONLY_PASSWORD"), "ssl": False}
    adopt_id = os.environ.get("METABASE_ADOPT_DATABASE_ID")
    if adopt_id:
        # Explicit recovery for an interrupted create-before-marker update. Never adopt by name alone.
        database = api.call("GET", f"/database/{int(adopt_id)}")
        matches = [item for item in databases if item.get("name") == "Crash-cache read-only"]
        same_connection = all(database.get("details", {}).get(key) == details[key]
                              for key in ("host", "port", "dbname", "user"))
        if (len(matches) != 1 or matches[0]["id"] != database["id"]
                or database.get("name") != "Crash-cache read-only"
                or database.get("engine") != "postgres" or not same_connection
                or (database.get("description") or "") not in ("", MARKER)):
            raise ProvisionError("Explicit database adoption does not match the expected unmarked read-only source")
    else:
        database = unique_managed(databases, "Crash-cache read-only")
    body = {"name": "Crash-cache read-only", "engine": "postgres", "details": details,
            "is_full_sync": False, "is_on_demand": False}
    if database:
        database = api.call("PUT", f"/database/{database['id']}", {**body, "description": MARKER})
    else:
        database = api.call("POST", "/database", body)
        # POST /database deliberately omits description; PUT /database/:id persists it.
        database = api.call("PUT", f"/database/{database['id']}", {"description": MARKER})
    collection = unique_managed(rows(api.call("GET", "/collection")), COLLECTION)
    if not collection:
        collection = api.call("POST", "/collection", {"name": COLLECTION, "description": MARKER})
    collection_id = collection["id"]
    cards = rows(api.call("GET", "/card"))
    card_ids = []
    for name, query in zip(CARD_NAMES, load_queries()):
        card = unique_managed(cards, name, collection_id)
        body = {"name": name, "description": MARKER, "collection_id": collection_id,
                "display": "table", "visualization_settings": {},
                "dataset_query": {"database": database["id"], "type": "native",
                                  "native": {"query": query, "template-tags": template_tags(project_id, start, end)}}}
        card = api.call("PUT", f"/card/{card['id']}", body) if card else api.call("POST", "/card", body)
        result = api.call("POST", f"/card/{card['id']}/query", {"parameters": query_parameters(project_id, start, end)})
        if result.get("status") != "completed":
            raise ProvisionError(f"Question execution failed: {name}")
        card_ids.append(card["id"])
    dashboard = unique_managed(rows(api.call("GET", "/dashboard")), DASHBOARD, collection_id)
    if not dashboard:
        dashboard = api.call("POST", "/dashboard", {"name": DASHBOARD, "description": MARKER, "collection_id": collection_id})
    current = api.call("GET", f"/dashboard/{dashboard['id']}")
    existing = {item["card_id"]: item["id"] for item in current.get("dashcards", []) if item.get("card_id")}
    dashcards = []
    for index, card_id in enumerate(card_ids):
        dashcards.append({"id": existing.get(card_id, -(index + 1)), "card_id": card_id,
                          "row": index * 6, "col": 0, "size_x": 24, "size_y": 6,
                          "visualization_settings": {}, "series": [],
                          "parameter_mappings": [
                              {"parameter_id": name, "card_id": card_id,
                               "target": ["variable", ["template-tag", name]]}
                              for name in ("project_id", "from", "until")]})
    parameters = [
        {"id": "project_id", "name": "Project", "slug": "project", "type": "number/=", "default": [project_id]},
        {"id": "from", "name": "From (inclusive)", "slug": "from", "type": "date/single", "default": start},
        {"id": "until", "name": "Until (exclusive)", "slug": "until", "type": "date/single", "default": end},
    ]
    api.call("PUT", f"/dashboard/{dashboard['id']}", {"parameters": parameters, "dashcards": dashcards})
    return dashboard["id"], card_ids


def main():
    api = Api(required("METABASE_URL"))
    today = dt.date.today()
    project_id = int(required("CRASH_CACHE_PROJECT_ID"))
    start = os.environ.get("OBSERVABILITY_FROM", (today - dt.timedelta(days=30)).isoformat())
    end = os.environ.get("OBSERVABILITY_UNTIL", (today + dt.timedelta(days=1)).isoformat())
    if project_id <= 0 or dt.date.fromisoformat(start) >= dt.date.fromisoformat(end):
        raise ProvisionError("Provide a positive project and an increasing ISO date range")
    try:
        dashboard_id, cards = provision(api, project_id, start, end)
        print(json.dumps({"dashboard_id": dashboard_id, "card_ids": cards,
                          "url": f"{api.base}/dashboard/{dashboard_id}"}))
    finally:
        if api.session:
            api.call("DELETE", "/session", {"metabase-session-id": api.session})


if __name__ == "__main__":
    try:
        main()
    except (ProvisionError, ValueError, KeyError) as error:
        print(f"Provisioning failed: {error}", file=sys.stderr)
        sys.exit(1)
