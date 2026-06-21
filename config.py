from collections.abc import Callable
from dataclasses import dataclass, KW_ONLY
from typing import Any

class ConfigSchema:
    __slots__ = ("config", "version")

    @dataclass
    class ConfigValue:
        decoder: Callable
        default: Any
        _: KW_ONLY
        version: int

    def __init__(self):
        self.config: dict[str, ConfigValue] = {}
        self.version = 0

    def add(self, value: str, *args, **kwargs):
        opt = ConfigSchema.ConfigValue(*args, **kwargs)
        self.config[value] = opt
        self.version = max(self.version, opt.version)
        return self

KNOWN_CONFIG_SCHEMA = ConfigSchema() \
        .add("version", int, 0, version = 0) \
        .add("no_checking", bool, True, version = 1)

def generate_new_config_file(config_name: str | None = None):
    config: dict = {}
    for key, value in KNOWN_CONFIG_SCHEMA.config.items():
        config[key] = value.default

    config["version"] = KNOWN_CONFIG_SCHEMA.version
    conf_filename = "config.toml" if config_name is None else config_name + ".toml"
    with open(conf_filename, "w") as file:
        for key, value in config.items():
            file.write(f"{key} = {value}\n")

if __name__ == "__main__":
    response = input("Enter config name (defaults to `config`): ")
    if response == "":
        print("Generating default config file...")
        generate_new_config_file()
        print("Check the current directory")
    else:
        print(f"Generating config file for `{response}`...")
        generate_new_config_file(response)
        print("Check the current directory")

