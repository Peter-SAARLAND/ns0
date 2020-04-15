import datetime
import logging
import os

import dns.resolver
import logzero
import tldextract
from config import ConfigResolver, DictConfigSource
from lexicon import discovery
from logzero import logger
from providers.docker import Docker
from providers.lexicon import LexiconClient

# We respect Lexicons Config here
TLDEXTRACT_CACHE_FILE_DEFAULT = os.path.join("~", ".lexicon_tld_set")
TLDEXTRACT_CACHE_FILE = os.path.expanduser(
    os.environ.get("LEXICON_TLDEXTRACT_CACHE", TLDEXTRACT_CACHE_FILE_DEFAULT)
)

logzero.loglevel(logging.INFO)


class NS0:
    """
    NS0 Base Class

    The ns0 Nameserver Object has the following properties:
    - Endpoints: upon initialization, ns0 discovers a set of possible IP subnets
      it might be in and defines corresponding endpoints:
        * ddns: the external IP discovered (if any)
        * private: the private network IP discovered (if any)
        * docker: the IPs of the container (if any)
        * zerotier: optionally a ZeroTier IP

        Containers can pick any of these Endpoints by setting the
        `ns0.endpoints=private, zerotier` label. The requested record
        will be published with the respective Endpoint-IP.
    - DDNS: if configured, ns0 will keep its current external IP adress in Sync with a
    """

    records = {
        "here.ns0.co": {
            "endpoints": ["local"],
            "sources": [{"name": "system", "type": "ns0", "id": "1"}],
            "found": datetime.datetime.now(),
            "ttl": 0,
        },
        "*.here.ns0.co": {
            "endpoints": ["local"],
            "sources": [{"name": "system", "type": "ns0", "id": "1"}],
            "found": datetime.datetime.now(),
            "ttl": 0,
        },
    }

    default_config = {
        "ttl": 10,
        "update_interval": 10,
    }

    def __init__(self):
        logger.info("Initalizing ns0 ...")

        self.config = ConfigResolver()
        self.config.with_env().with_dict(self.default_config)

        # Guess available Endpoints
        # This includes Endpoints defined in the configuration
        endpoints = self.guessEndpoints()
        self.config.add_config_source(DictConfigSource(endpoints))

        print(self.config.resolve("ns0:endpoints"))

        if self.config:
            logger.info("Loaded initial Configuration")
        else:
            logger.error("Error loading initial configuration")

        logger.info("Available Endpoints:")

        for endpoint in self.config.resolve("ns0:endpoints"):
            logger.info(
                "{}:\t{}".format(
                    endpoint, self.config.resolve("ns0:endpoints:{}".format(endpoint))
                )
            )

        self.docker = Docker()
        self.update()

    def update(self):
        # Guess Endpoints
        endpoints = self.guessEndpoints()

        self.config.add_config_source(DictConfigSource(endpoints))

        # Get latest Records from sources
        records = self.docker.getRecords()

        # Update self.records
        updates = self.createRecords(records)
        return updates

    def clean(self):
        """Garbage Collection for expired Records"""
        expired = []

        for record in self.records:
            now = datetime.datetime.now()

            # Get Default TTL
            ttl = self.config.resolve("ns0:ttl")

            # Check if the record has a specific TTL set
            if "ttl" in self.records[record]:
                ttl = self.records[record]["ttl"]

            # Check difference between update_interval and ttl
            # If update_interval is close to ttl (or higher), ns0 gets locked
            # in a DELETE/CREATE loop
            treshhold = 5
            update_interval = self.config.resolve("ns0:update_interval")

            # Examples:
            # ttl: 10
            # update_interval: 10
            # treshhold: 5
            #
            # ttl: 10
            # update_interval: 60
            # treshhold: 55
            if update_interval >= ttl:
                treshhold = treshhold + (update_interval - ttl)

            # If TTL is 0, we don't expire the record
            delta = int((now - self.records[record]["found"]).total_seconds())
            if ttl != 0 and delta >= (ttl + treshhold):
                # Record is over its TTL
                logger.warning(
                    "Record {} expired. TTL: {}. Delta: {}".format(record, ttl, delta)
                )
                expired.append(record)

        deletion = self.deleteRecords(expired)
        return deletion

    def deleteRecords(self, records):
        error = False
        for record in records:
            # When looping over `records` we're getting the dict key
            # aka `record_name`
            record_name = record

            # Set Hostname
            # Set Endpoints
            # Set Sources
            # Set Found
            # Set TTL
            hostname = record_name
            guess = self.guessDomain(hostname)
            domain = "{}.{}".format(guess.domain, guess.suffix)
            name = guess.subdomain

            provider_name = ""
            if "provider" in self.records[record_name]:
                provider_name = self.records[record_name]["provider"]
            else:
                # Guess DNS provider from Hostname
                provider_name = self.guessProvider(hostname)[0]
            endpoints = self.records[record_name]["endpoints"]

            # hostname should be deleted
            # DELETE
            # We're invoking Lexicon to delete a Record for each endpoint
            # our Record specifies
            for endpoint in endpoints:
                # Now we involve Lexicon
                # Lexicon works in an idempotent way already - it checks
                # if the record already exists before creating it
                # - at least this behaviour is required by the providers
                # That's why we can simply 'create' here, without further checks
                # provider_name, action, domain, name, type, content
                lex = LexiconClient(
                    provider_name,  # provider_name
                    "delete",  # action
                    domain,  # domain
                    name,  # name
                    "A",  # type
                    self.endpoints[endpoint],  # content (e.g. endpoint IP)
                )

                try:
                    lex.execute()
                    logger.debug(
                        "{}: Record {} deleted from Running Config".format(
                            provider_name, record
                        )
                    )

                    del self.records[record]
                    logger.debug(
                        "{}: Record {} deleted from Running Config".format(
                            provider_name, record
                        )
                    )
                except Exception as e:
                    error = True
                    logger.exception(
                        "{}: failed to delete Record {} with Lexicon: {}".format(
                            provider_name, record, e
                        )
                    )

        return error or True

    def createRecords(self, records):
        error = False
        # TARGET DICT
        # "here.ns0.co": {
        #     "endpoints": ["local"],
        #     "sources": [{"name": "system", "type": "ns0", "id": "1"}],
        #     "found": datetime.datetime.now(),
        #     "ttl": 0,
        # },
        if records:
            for record in records:

                # When looping over `records` we're getting the dict key
                # aka `record_name`
                record_name = record

                # Set Hostname
                # Set Endpoints
                # Set Sources
                # Set Found
                # Set TTL
                hostname = records[record_name]["hostname"]
                guess = self.guessDomain(hostname)
                domain = "{}.{}".format(guess.domain, guess.suffix)
                name = guess.subdomain
                provider_name = ""
                if "provider" in records[record_name]:
                    provider_name = records[record_name]["provider"]
                else:
                    # Guess DNS provider from Hostname
                    provider_name = self.guessProvider(hostname)[0]

                endpoints = records[record_name]["endpoints"]
                sources = records[record_name]["sources"]
                found = datetime.datetime.now()
                ttl = self.config.resolve("ns0:ttl")

                # Check if hostname is already in records
                if hostname in self.records:
                    # hostname already exists in records
                    # UPDATE
                    # Check Endpoints
                    running_config_endpoints = len(self.records[hostname]["endpoints"])
                    incoming_config_endpoints = len(endpoints)

                    if running_config_endpoints != incoming_config_endpoints:
                        # Old and new Endpoints do not match
                        # Let's delete this record and re-scan
                        try:
                            logger.info(
                                "✓ Detected changes in Record Endpoints. \
                                    Deleting Record {}".format(
                                    hostname
                                )
                            )
                            self.deleteRecords([hostname])

                            # TODO: Trigger instant Re-Scan here
                        except Exception as e:
                            logger.exception(
                                "✗ {}: failed to delete Record {} \
                                    with Lexicon: {}".format(
                                    provider_name, e
                                )
                            )
                        continue

                    # Check sources
                    # Loop over existing and new sources,
                    # check if any of the id's match
                    # If nothing matches, add the new source to the array
                    for source in sources:
                        invalid = False
                        for e_source in self.records[hostname]["sources"]:
                            if (
                                source["id"] == e_source["id"]
                                and source["type"] == e_source["type"]
                            ):
                                invalid = True
                        if not invalid:
                            self.records[hostname]["sources"].append(source)

                    # Set found to current date so the record doesn't expire
                    self.records[hostname]["found"] = found
                else:
                    # hostname doesn't exist in records
                    # CREATE
                    self.records[hostname] = {
                        "endpoints": endpoints,
                        "sources": sources,
                        "found": found,
                        "ttl": ttl,
                    }

                    # We're invoking Lexicon to create a Record for each endpoint
                    # our Record specifies
                    for endpoint in endpoints:
                        for interface in self.config.resolve(
                            "ns0:endpoints:{}".format(endpoint)
                        ):
                            # Now we involve Lexicon
                            # Lexicon works in an idempotent way already - it checks
                            # if the record already exists before creating it
                            # - at least this behaviour is required by the providers
                            # That's why we can simply 'create' here, without further
                            # checks
                            type = "A"
                            if (
                                self.config.resolve(
                                    "ns0:endpoints:{}:{}".format(endpoint, interface)
                                )
                                == "ipv6"
                            ):
                                type = "AAAA"
                            lex = LexiconClient(
                                provider_name,  # provider_name
                                "create",  # action
                                domain,  # domain
                                name,  # name
                                type,  # type
                                self.config.resolve(
                                    "ns0:endpoints:{}:{}".format(endpoint, interface)
                                ),  # content (e.g. endpoint IP)
                            )

                        try:
                            create_result = lex.execute()

                            if create_result:
                                logger.debug(
                                    "{}: Record {} added to Running Config".format(
                                        provider_name, hostname
                                    )
                                )
                        except Exception as e:
                            error = True
                            logger.exception(
                                "{}: failed to create Record {} with Lexicon: {}".format(  # noqa: E501
                                    provider_name, hostname, e
                                )
                            )

            return error or True
        else:
            return False

    def guessDomain(self, hostname):
        extract = tldextract.TLDExtract(
            cache_file=TLDEXTRACT_CACHE_FILE, include_psl_private_domains=True
        )
        tld = extract(hostname)
        return tld

    def guessEndpoints(self):
        endpoints = {
            "private": {"ipv4": "127.0.0.1", "ipv6": "::1"},
            "public": {"ipv4": "127.0.0.1", "ipv6": "::1"},
            "ddns": {"ipv4": "127.0.0.1", "ipv6": "::1"},
            "local": {"ipv4": "127.0.0.1", "ipv6": "::1"},
            "zerotier": {"ipv4": "127.0.0.1", "ipv6": "::1"},
        }

        # Private Endpoint
        # Disabled for now, doesn't work in Docker
        # import socket

        # s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # s.connect(("8.8.8.8", 80))
        # private_ip = s.getsockname()[0]
        # endpoints["private"] = {}
        # endpoints["private"]["ipv4"] = private_ip
        # s.close()

        # Public Endpoint (ddns)
        from requests import get

        public_ipv4 = get("https://api.ipify.org").text
        public_ipv6 = get("https://api6.ipify.org").text
        endpoints["public"] = {}
        endpoints["ddns"] = {}
        endpoints["public"]["ipv4"] = public_ipv4
        endpoints["ddns"]["ipv4"] = public_ipv4

        if public_ipv6 and public_ipv6 != public_ipv4:
            endpoints["public"]["ipv6"] = public_ipv6
            endpoints["ddns"]["ipv6"] = public_ipv6

        return {"endpoints": endpoints}

    def guessProvider(self, hostname):
        domain = self.guessDomain(hostname)
        resolve = "{}.{}".format(domain.domain, domain.suffix)
        nameservers = dns.resolver.query(resolve, "NS")

        # 1 Get Lexicon Providers
        lexicon_providers = discovery.find_providers()

        valid_guesses = set([])

        # Loop over nameservers to find a Lexicon provider
        for nameserver in nameservers:
            # Remove trailing .
            nameserver = str(nameserver.target).strip()
            domain = self.guessDomain(str(nameserver).strip())
            extracted_provider = domain.domain
            lexicon_provider = lexicon_providers[extracted_provider]
            if lexicon_provider:
                valid_guesses.add(extracted_provider)
        return list(valid_guesses)
