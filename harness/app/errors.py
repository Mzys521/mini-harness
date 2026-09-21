# 文件：harness/app/errors.py
class HarnessAppError(RuntimeError):
    pass


class FeatureDependencyError(HarnessAppError):
    def __init__(self, feature: str, install_hint: str) -> None:
        super().__init__(
            f"Feature '{feature}' 缺少可选依赖。请执行：{install_hint}"
        )
        self.feature = feature
        self.install_hint = install_hint


class UnsafeServerConfigurationError(HarnessAppError):
    pass
