# ns0 - Container DNS

`ns0` is an **opinionated** DNS service for Containers. It watches the Docker Socket for events and updates DNS zones at [Lexicon-Supported Providers](https://github.com/AnalogJ/lexicon#providers) automatically.

## Features

* Define Records from Container-Labels
* Multiple [Endpoints](#endpoints) per Hostname
* Automatically records at [Lexicon-Supported Providers](https://github.com/AnalogJ/lexicon#providers)
* Can be run in Docker Swarm, Kubernetes, etc

### Endpoints

An **Endpoint** is an IP Address (IPv4 or IPv6) that is available to `ns0`. On Startup, `ns0` guesses available endpoints by means of some networking-foo. Currently supported Endpoints are:

* local (defaults to 127.0.0.1)
* private (defaults to the first non-Docker private IP found)
* public (defaults to the first non-Docker public IP found with [ipfy](https://api.ipify.org))
* ddns (same as public)
* zerotier (currently 127.0.0.1, TBD)

## Get Started

### Run ns0

`ns0` expects the Auth-Information for each DNS-Provider to be given as Environment Variables according to the [Lexicon specs](https://github.com/AnalogJ/lexicon#authentication).

`ns0` also needs access to the **Docker Socket** or it can't do much good as of now.

`docker run -e LEXICON_DIGITALOCEAN_AUTH_TOKEN=abc -v /var/run/docker.sock:/var/run/docker.sock registry.gitlab.com/peter.saarland/ns0:latest`

To instruct `ns0` to publish DNS-Records for a container, add these labels to the container or service:

```bash
ns0.subdomain.hostname=sub.domain.tld.com
ns0.subdomain.endpoints=public
```

## Roadmap

`ns0` will grow to a distributed, shared knowlegde DNS Server. Once the HTTP API and DNS Interface have been implemented, it can be used as an (opinionated) authoritive namserver. Additionally, a `ns0` cluster can be used as a central proxy for `ns0`-Clients to update DNS-Records at multiple providers from a single point of management (i.e. `ns0`-server holds all DNS-Provider info, `ns0`-client just authenticates to the server and not to each DNS-Provider).

* Split Providers properly, make them selectable by flag/config
* Add Zerotier-Provider
* Add API-Provider
* Add HTTP REST-API
* Add DNS Interface

## Development

* make sure `poetry` is installed
* git clone + cd to project directory
* `poetry shell`
* `code .`
* `poetry install`
