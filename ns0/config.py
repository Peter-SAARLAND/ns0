#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Definition of the ConfigResolver to configure ns0,
and convenient classes to build various configuration sources.
"""
import os
import re
import warnings

import yaml
from logzero import logger


class ConfigResolver(object):  # pylint: disable=useless-object-inheritance
    """
    Highly customizable configuration resolver object, that gets
    configuration parameters from various sources with a precedence order.
    Sources and their priority are configured by calling the with* methods
    of this object, in the decreasing priority order.
    A configuration parameter can be retrieved using the resolve() method.
    The configuration parameter key needs to conform to a namespace,
    whose delimeters is ':'. Two namespaces will be used in the context of ns0:
        * parameters relevant for ns0 itself: 'ns0:global_parameter'
        * parameters specific to a provider: 'ns0:cloudflare:param'
    Example:
        # This will resolve configuration parameters from environment variables,
        # then from a configuration file named '/my/path/to/ns0.yml'.
        $ from ns0.config import ConfigResolver
        $ config = ConfigResolver()
        $ config.with_env().with_config_file()
        $ print(config.resolve('ns0:delegated'))
        $ print(config.resolve('ns0:cloudflare:auth_token))
    Config can resolve parameters for ns0 and providers from:
        * environment variables
        * arguments parsed by ArgParse library
        * YAML configuration files, generic or specific to a provider
        * any object implementing the underlying ConfigSource class
    Each parameter will be resolved against each source, and value from the
    higher priority source is returned. If a parameter could not be resolve
    by any source, then None will be returned.
    """

    def __init__(self):
        super(ConfigResolver, self).__init__()
        self._config_sources = []

    def resolve(self, config_key):
        """
        Resolve the value of the given config parameter key. Key must be
        correctly scoped for ns0, and optionally for the DNS provider for
        which the parameter is consumed.

        For instance:
            * config.resolve('ns0:delegated') will get the delegated parameter for ns0
            * config.resolve('ns0:cloudflare:auth_token') will get the
            auth_token parameter consumed by cloudflare DNS provider.
        Value is resolved against each configured source, and value from the
        highest priority source is returned. None will be returned if the given
        config parameter key could not be resolved from any source.
        """
        for config_source in self._config_sources:
            value = config_source.resolve(config_key)
            if value:
                return value

        return None

    def add_config_source(self, config_source, position=None):
        """
        Add a config source to the current ConfigResolver instance.
        If position is not set, this source will be inserted with the lowest priority.
        """
        rank = position if position is not None else len(self._config_sources)
        self._config_sources.insert(rank, config_source)

    def with_config_source(self, config_source):
        """
        Configure current resolver to use the provided ConfigSource instance
        to be used as a source.
        See documentation of ConfigSource to see how to
        implement correctly a ConfigSource.
        """
        self.add_config_source(config_source)
        return self

    def with_env(self):
        """
        Configure current resolver to use available environment variables as a source.
        Only environment variables starting with 'NS0' or 'NS0_[PROVIDER]'
        will be taken into account.
        """
        return self.with_config_source(EnvironmentConfigSource())

    def with_args(self, argparse_namespace):
        """
        Configure current resolver to use a Namespace object given by a
        ArgParse instance using arg_parse() as a source. This method is typically
        used to allow a ConfigResolver to get parameters from the command line.
        It is assumed that the argument parser have already checked that
        provided arguments are valid for ns0 or the current provider. No further
        namespace check on parameter keys will be done here. Meaning that if
        'ns0:cloudflare:auth_token' is asked, any auth_token present in the given
        Namespace object will be returned.
        """
        return self.with_config_source(ArgsConfigSource(argparse_namespace))

    def with_dict(self, dict_object):
        """
        Configure current resolver to use the given dict object,
        scoped to ns0 namespace.
        Example of valid dict object for ns0:
            {
                'delegated': 'onedelegated',
                'cloudflare': {
                    'auth_token': 'SECRET_TOKEN'
                }
            }
            => Will define properties 'ns0:delegated' and 'ns0:cloudflare:auth_token'
        """
        return self.with_config_source(DictConfigSource(dict_object))

    def with_config_file(self, file_path):
        """
        Configure current resolver to use a YAML configuration file specified on
        the given path. This file provides configuration parameters for ns0 a
        nd any DNS provider.
        Typical format is:
            $ cat ns0.yml
            # Will define properties 'ns0:delegated' and 'ns0:cloudflare:auth_token'
            delegated: 'onedelegated'
            cloudflare:
            auth_token: SECRET_TOKEN
        """
        return self.with_config_source(FileConfigSource(file_path))

    def with_provider_config_file(self, provider_name, file_path):
        """
        Configure current resolver to use a YAML configuration file specified
        on the given path.
        This file provides configuration parameters for a DNS provider exclusively.
        Typical format is:
            $ cat ns0_cloudflare.yml
            # Will define properties 'ns0:cloudflare:auth_token'
            # and 'ns0:cloudflare:auth_username'
            auth_token: SECRET_TOKEN
            auth_username: USERNAME
        NB: If file_path is not specified, '/etc/ns0/ns0_[provider].yml' will be taken
        by default, with [provider] equals to the given provider_name parameter.
        """
        return self.with_config_source(
            ProviderFileConfigSource(provider_name, file_path)
        )

    def with_config_dir(self, dir_path):
        """
        Configure current resolver to use every valid YAML configuration
        files available in the given directory path. To be taken into account,
        a configuration file must conform to the following naming convention:
            * 'ns0.yml' for a global ns0 config file (see with_config_file doc)
            * 'ns0_[provider].yml' for a DNS provider specific configuration file, with
            [provider] equals to the DNS provider name
            (see with_provider_config_file doc)
        Example:
            $ ls /etc/ns0
            ns0.yml # global ns0 configuration file
            ns0_cloudflare.yml # specific configuration file for clouflare DNS provder
        """
        ns0_provider_config_files = []
        ns0_config_files = []

        for path in os.listdir(dir_path):
            path = os.path.join(dir_path, path)
            if os.path.isfile(path):
                basename = os.path.basename(path)
                search = re.search(r"^ns0(?:_(\w+)|)\.yml$", basename)
                if search:
                    provider = search.group(1)
                    if provider:
                        ns0_provider_config_files.append((provider, path))
                    else:
                        ns0_config_files.append(path)

        for ns0_provider_config_file in ns0_provider_config_files:
            self.with_provider_config_file(
                ns0_provider_config_file[0], ns0_provider_config_file[1]
            )

        for ns0_config_file in ns0_config_files:
            self.with_config_file(ns0_config_file)

        return self

    def with_legacy_dict(self, legacy_dict_object):
        """Configure a source that consumes the dict that where used on ns0 2.x"""
        warnings.warn(
            DeprecationWarning(
                "Legacy configuration object has been used "
                "to load the ConfigResolver."
            )
        )
        return self.with_config_source(LegacyDictConfigSource(legacy_dict_object))


class ConfigSource(
    object
):  # pylint: disable=useless-object-inheritance,too-few-public-methods
    """
    Base class to implement a configuration source for a ConfigResolver.
    The relevant method to override is resolve(self, config_parameter).
    """

    def resolve(self, config_key):
        """
        Using the given config_parameter value (in the form of 'ns0:config_key' or
        'ns0:[provider]:config_key'), try to get the associated value.
        None must be returned if no value could be found.
        Must be implemented by each ConfigSource concrete child class.
        """
        raise NotImplementedError(
            "The method resolve(config_key) "
            "must be implemented in the concret sub-classes."
        )


class EnvironmentConfigSource(ConfigSource):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against existing environment variables"""

    def __init__(self):
        super(EnvironmentConfigSource, self).__init__()
        self._parameters = {}
        for (key, value) in os.environ.items():
            if key.startswith("NS0_"):
                self._parameters[key] = value

    def resolve(self, config_key):
        # First try, with a direct conversion of the config_parameter:
        #   * ns0:provider:auth_my_config => NS0_PROVIDER_AUTH_MY_CONFIG
        #   * ns0:provider:my_other_config => NS0_PROVIDER_AUTH_MY_OTHER_CONFIG
        #   * ns0:my_global_config => NS0_MY_GLOBAL_CONFIG
        environment_variable = re.sub(":", "_", config_key).upper()
        value = self._parameters.get(environment_variable, None)
        if value:
            return value

        # Second try, with the legacy naming convention for specific provider config:
        #   * ns0:provider:auth_my_config => NS0_PROVIDER_MY_CONFIG
        # Users get a warning about this deprecated usage.
        environment_variable_legacy = re.sub(
            r"(.*)_AUTH_(.*)", r"\1_\2", environment_variable
        ).upper()
        value = self._parameters.get(environment_variable_legacy, None)
        if value:
            logger.warning(
                (
                    "Warning: Use of environment variable %s is deprecated. "
                    "Try %s instead."
                ),
                environment_variable_legacy,
                environment_variable,
            )
            return value

        return None


class ArgsConfigSource(ConfigSource):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against an argparse namespace."""

    def __init__(self, namespace):
        super(ArgsConfigSource, self).__init__()
        self._parameters = vars(namespace)

    def resolve(self, config_key):
        # We assume here that the namespace provided has already done its job,
        # by validating that all given parameters are
        # relevant for ns0 or the current provider.
        # So we ignore the namespaces 'ns0:' and 'ns0:provider' in given config key.
        splitted_config_key = config_key.split(":")

        return self._parameters.get(splitted_config_key[-1], None)


class DictConfigSource(ConfigSource):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against a dict object."""

    def __init__(self, dict_object):
        super(DictConfigSource, self).__init__()
        self._parameters = dict_object

    def resolve(self, config_key):
        splitted_config_key = config_key.split(":")
        # Note that we ignore 'NS0:' in the iteration,
        # as the dict object is already scoped to ns0.
        cursor = self._parameters
        for current in splitted_config_key[1:-1]:
            cursor = cursor.get(current, {})

        return cursor.get(splitted_config_key[-1], None)


class FileConfigSource(DictConfigSource):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against a lexicon config file."""

    def __init__(self, file_path):
        with open(file_path, "r") as stream:
            yaml_object = yaml.load(stream) or {}

        super(FileConfigSource, self).__init__(yaml_object)


class ProviderFileConfigSource(
    FileConfigSource
):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against an provider config file."""

    def __init__(self, provider_name, file_path):
        super(ProviderFileConfigSource, self).__init__(file_path)
        # Scope the loaded config file into provider namespace
        self._parameters = {provider_name: self._parameters}


class LegacyDictConfigSource(
    DictConfigSource
):  # pylint: disable=too-few-public-methods
    """ConfigSource that resolve configuration against a legacy 2.x dict object"""

    def __init__(self, dict_object):
        provider_name = dict_object.get("provider_name") or dict_object.get("provider")
        if not provider_name:
            raise AttributeError(
                "Error, key provider_name is not defined."
                "LegacyDictConfigSource cannot scope correctly "
                "the provider specific options."
            )

        generic_parameters = [
            "domain",
            "action",
            "provider_name",
            "delegated",
            "identifier",
            "type",
            "name",
            "content",
            "ttl",
            "priority",
            "log_level",
            "output",
        ]

        provider_options = {}
        refactor_dict_object = {}
        refactor_dict_object[provider_name] = provider_options

        for (key, value) in dict_object.items():
            if key not in generic_parameters:
                provider_options[key] = value
            else:
                refactor_dict_object[key] = value

        super(LegacyDictConfigSource, self).__init__(refactor_dict_object)


def non_interactive_config_resolver():
    """
    Create a typical config resolver in a non-interactive context
    (eg. ns0 used as a library).
    Configuration will be resolved againts env variables and ns0
    config files in working dir.
    """
    return ConfigResolver().with_env().with_config_dir(os.getcwd())


def legacy_config_resolver(legacy_dict):
    """
    With the old legacy approach, we juste got a plain configuration dict object.
    Custom logic was to enrich this configuration with env variables.
    This function create a resolve that respect the expected behavior,
    by using the relevant ConfigSources, and we add the config files
    from working directory.
    """
    return (
        ConfigResolver()
        .with_legacy_dict(legacy_dict)
        .with_env()
        .with_config_dir(os.getcwd())
    )
