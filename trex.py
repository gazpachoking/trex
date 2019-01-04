import re

from flask import Flask, request, json

app = Flask(__name__)


@app.route("/trakt_hook", methods=["POST"])
def hook_receiver():
    payload = json.loads(request.form["payload"])
    # Let's only handle the scrobble event for now.
    if payload["event"] != "media.scrobble":
        return ""
    scrobble_object = create_scrobble_object(payload)
    if not scrobble_object:
        return "Unable to form trakt request.", 500
    return ""


def create_scrobble_object(plex_payload):
    result = {}
    if plex_payload["Metadata"]["type"] == "movie":
        movie = result["movie"] = {}
        movie["title"] = plex_payload["Metadata"]["title"]
        movie["year"] = plex_payload["Metadata"]["year"]
        imdb_match = re.match(
            r"imdb://(?P<imdb_id>tt\d+)", plex_payload["Metadata"]["guid"]
        )
        if imdb_match:
            movie["ids"] = {"imdb": imdb_match.group("imdb_id")}
    elif plex_payload["Metadata"]["type"] == "episode":
        show = result["show"] = {}
        episode = result["episode"] = {}
        show["title"] = plex_payload["Metadata"]["grandparentTitle"]
        episode["title"] = plex_payload["Metadata"]["title"]
        tvdb_match = re.match(
            r"thetvdb://(?P<tvdb_id>\d+)/(?P<season>\d+)/(?P<episode>\d+)",
            plex_payload["Metadata"]["guid"],
        )
        if tvdb_match:
            show["ids"] = {"tvdb": int(tvdb_match.group("tvdb_id"))}
            episode["season"] = int(tvdb_match.group("season"))
            episode["number"] = int(tvdb_match.group("episode"))
        else:
            episode["season"] = plex_payload["Metadata"]["parentIndex"]
            episode["number"] = plex_payload["Metadata"]["index"]
    return result or None


if __name__ == "__main__":
    app.run(host="0.0.0.0")
