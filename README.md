# Trex 
Small script which can handle Plex scrobble webhooks and log them to trakt.

## Usage

Add a new webhook to Plex with the url `http://<your server>:5000/trakt_hook`  

```sh
trex.py authenticate <plex username>
```

Starts authentication to trakt.tv and records the oauth token in trex config
file. Follow the instructions to complete the authentication. Any plex plays by
<plex username> will then be scrobbled to the authenticated trakt account.

```sh
trex.py run
```

Starts the web server which handles the plex webhook.
