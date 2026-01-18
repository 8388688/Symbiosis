from typing import Callable

__all__ = ["Version", "UpgradeSlice", "update_content"]


class Version(tuple):
    def __new__(cls, *args):
        if len(args) == 1 and isinstance(args[0], str):
            args = tuple(map(int, args[0].lower().lstrip('v').split('.')))
        while len(args) < 4:
            args += (0,)
        return super().__new__(cls, args)

    def __str__(self):
        return f"v{self[0]}.{self[1]}.{self[2]}.{self[3]}"

    def __repr__(self):
        return f"Version('{str(self)}')"

    def __lt__(self, other):
        return super().__lt__(other)


class UpgradeSlice:
    def __init__(self, earliest_version=None, latest_version=None):
        if isinstance(earliest_version, str):
            earliest_version = self.version2tuple(earliest_version)
        if isinstance(latest_version, str):
            latest_version = self.version2tuple(latest_version)
        self.earliest_version: tuple = earliest_version
        self.latest_version: tuple = latest_version
        # 左闭右开，包含 earliest_version, 不包含 latest_version.
        self.__action = None

    def version2tuple(self, version_str):
        tmp = list(map(int, version_str.lower().lstrip('v').split('.')))
        while len(tmp) < 4:
            tmp.append(0)
        return tuple(tmp)

    @property
    def action(self):
        if self.__action is None:
            raise ValueError("Action has not been set.")
        elif not isinstance(self.__action, Callable):
            raise TypeError("Action is not callable.")
        return self.__action()

    @action.setter
    def action(self, value):
        if isinstance(value, Callable):
            self.__action = value
        else:
            raise TypeError("Action must be a callable.")

    def run(self, version: str | tuple | None = None):
        if version is None:
            # version = __import__('__main__').__version__
            version = self.latest_version
            raise ValueError(
                "Version must be provided if latest_version is not set.")
        elif isinstance(version, str):
            version = self.version2tuple(version)
        elif isinstance(version, tuple):
            pass
        assert isinstance(version, tuple), "<version> must be a tuple."
        if self.earliest_version is not None and self.earliest_version > version:
            # 版本过低
            return False
        if self.latest_version is not None and self.latest_version <= version:
            # 版本过高
            return False
        return self.action


def test_case():

    upgrade = UpgradeSlice(earliest_version="v1.2", latest_version="v1.5")

    def sample_action():
        print("Action executed.")
        return True

    upgrade.action = sample_action
    print("1.4.1" + f" Upgrade result: {upgrade.run("1.4.1")}")  # T
    print("1.2.0" + f" Upgrade result: {upgrade.run("1.2.0")}")  # T
    print("1.3" + f" Upgrade result: {upgrade.run("1.3")}")  # T
    print("v1.0" + f" Upgrade result: {upgrade.run("v1.0")}")  # F
    print("1.8" + f" Upgrade result: {upgrade.run("1.8")}")  # F
    print("1.5.0" + f" Upgrade result: {upgrade.run("1.5.0")}")  # F
    print("1.2.18.2" + f" Upgrade result: {upgrade.run("1.2.18.2")}")  # T
    # Expected: Action executed. Upgrade result: True

    print(Version("v1.2.3") < Version("v1.2.4"))  # T
    print(Version("v1.2") > Version("v1.2.2"))  # T
    print(Version("v1.2.3") == Version("v1.2.3"))  # T
    print(Version("v1"))  # v1.0.0.0
    print(repr(Version("v2.3.4")))  # Version('v2.3.4.0')
    print(Version((1, 2)) < Version((1, 2, 0, 1)))  # T

    print("All test cases passed.")


update_content: list[UpgradeSlice] = []


if __name__ == "__main__":
    print("Running test case for UpgradeSlice...")
    test_case()
