import time
from ...config_manager import ConfigManager


def test_config_hot_reload(tmp_path):
    state = {"version": 1}

    def loader():
        return {"config_version": f"v{state['version']}"}

    cm = ConfigManager(loader, poll_interval=1)
    # initial
    assert cm.config.config_version == "v1"
    # simulate change
    state["version"] = 2
    cm._reload()
    assert cm.config.config_version == "v2"
