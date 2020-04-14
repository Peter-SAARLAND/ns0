from lexicon.client import Client as LexClient
from lexicon.config import ConfigResolver as LexiconConfigResolver
from logzero import logger


class LexiconClient:
    def __init__(self, provider_name, action, domain, name, type, content):

        self.lexicon_config = {
            "provider_name": provider_name,
            "action": action,
            "domain": domain,
            "name": name,
            "type": type,
            "content": content,
        }
        # print(self.lexicon_config)
        self.config = LexiconConfigResolver()
        self.config.with_env().with_dict(dict_object=self.lexicon_config)

        self.client = LexClient(self.config)

        self.auth_token = self.config.resolve(
            "lexicon:{}:auth_token".format(self.lexicon_config["provider_name"])
        )

    def execute(self):
        # Check provider config before doing stuff
        results = ""
        if self.auth_token:
            results = self.client.execute()
            # print(results)
            if results:
                logger.info(
                    "✓ {}: {} Record {} -> {}".format(
                        self.config.resolve("lexicon:provider_name"),
                        self.config.resolve("lexicon:action").upper(),
                        self.config.resolve("lexicon:name")
                        + "."
                        + self.config.resolve("lexicon:domain"),
                        self.config.resolve("lexicon:content"),
                    )
                )
            else:
                logger.error("Couldn't create Record: {}".format(results))
        else:
            logger.error(
                "✗ {}: Missing auth_token. {} Record {} -> {} failed".format(
                    self.config.resolve("lexicon:provider_name"),
                    self.config.resolve("lexicon:action").upper(),
                    self.config.resolve("lexicon:name")
                    + "."
                    + self.config.resolve("lexicon:domain"),
                    self.config.resolve("lexicon:content"),
                )
            )
            results = False
        return results
