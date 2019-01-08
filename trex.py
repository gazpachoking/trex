import pathlib
import re
import time

import click
from flask import Flask, request, json
import requests
import yaml


app = Flask(__name__)

VERSION = "0.9"
TRAKT_API_URL = "https://api.trakt.tv/"
CLIENT_ID = "8c71f6ec3edb171968a4eda044b69d448edc64c0796f33a4ebf35d3e109138be"
CLIENT_SECRET = "a5320f59bbde92a36488560fb0b41a93730b36e4707b20371b39c194953bbe42"
CONFIG_FILE = None
HEADERS = {"trakt-api-version": "2", "trakt-api-key": CLIENT_ID}


@app.route("/trakt_hook", methods=["POST"])
def hook_receiver():
    config = load_config()
    payload = json.loads(request.form["payload"])
    # Let's only handle the scrobble event for now.
    if payload["event"] != "media.scrobble":
        return ""
    plex_user = payload["Account"]["title"]
    if plex_user not in config:
        return "Plex user not configured"
    access_token = config[plex_user]["access_token"]
    scrobble_object = create_scrobble_object(payload)
    if not scrobble_object:
        return "Unable to form trakt request.", 500
    scrobble_object.update({
        "progress": 100,
        "app_version": VERSION,

    })
    headers = {"Authorization": "Bearer {}".format(access_token)}
    headers.update(HEADERS)
    requests.post(
        TRAKT_API_URL + 'scrobble/stop',
        json=scrobble_object,
        headers=headers
    )
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


def load_config():
    configfile = pathlib.Path(CONFIG_FILE)
    with configfile.open('r') as f:
        return yaml.safe_load(f.read())


def save_config(config):
    configfile = pathlib.Path(CONFIG_FILE)
    with configfile.open('w') as f:
        return yaml.dump(config, f, default_flow_style=False)


@click.group()
@click.option('--config', '-c', default='./trex.yaml')
def cli(config):
    global CONFIG_FILE
    CONFIG_FILE = config


@cli.command()
def run():
    app.run(host="0.0.0.0")


@cli.command()
@click.argument('username', required=False)
def authenticate(username=None):
    if not username:
        username = click.prompt("Enter plex username")
    data = {'client_id': CLIENT_ID}
    try:
        r = requests.post(TRAKT_API_URL + 'oauth/device/code', data=data).json()
        device_code = r['device_code']
        user_code = r['user_code']
        expires_in = r['expires_in']
        interval = r['interval']

        click.echo('Please visit {0} and authorize Flexget. Your user code is {1}. Your code expires in '
                '{2} minutes.'.format(r['verification_url'], user_code, expires_in / 60.0))

        data['code'] = device_code
        data['client_secret'] = CLIENT_SECRET
        end_time = time.time() + expires_in
        click.echo('Waiting...', nl=False)
        result = None
        # stop polling after expires_in seconds
        while time.time() < end_time:
            time.sleep(interval)
            polling_request = requests.post(TRAKT_API_URL + 'oauth/device/token', data=data)
            if polling_request.status_code == 200:  # success
                result = polling_request.json()
                break
            elif polling_request.status_code == 400:  # pending -- waiting for user
                click.echo('...', nl=False)
            elif polling_request.status_code == 404:  # not found -- invalid device_code
                click.echo('Invalid device code.')
                break
            elif polling_request.status_code == 409:  # already used -- user already approved
                click.echo('User code has already been approved.')
                break
            elif polling_request.status_code == 410:  # expired -- restart process
                break
            elif polling_request.status_code == 418:  # denied -- user denied code
                click.echo('User code has been denied.')
                break
            elif polling_request.status_code == 429:  # polling too fast
                click.echo('Polling too quickly. Upping the interval. No action required.')
                interval += 1
        if not result:
            click.echo('Unable to authenticate. Please try again.')
            return
    except requests.RequestException as e:
        click.echo('Device authorization with Trakt.tv failed: {0}'.format(e))
        return
    config = load_config()
    config[username] = result
    save_config(config)


if __name__ == "__main__":
    cli(obj={})
