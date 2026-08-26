"""
TODOBA Customer MT5 Setup Preflight Service

Discovers customer-side MetaTrader 5 installations and
performs a read-only preflight against exactly one selected
terminal.

R4 responsibilities:

- discover standard MT5 installations from:
    %APPDATA%\\MetaQuotes\\Terminal\\*\\origin.txt
- expose exact terminal64.exe candidates
- probe only the terminal explicitly selected by the customer
- read authoritative terminal and current-account information
- build the canonical TODOBA account fingerprint:
    <ACCOUNT_SERVER>:<ACCOUNT_LOGIN>
- require MT5 HEDGING mode before commercial provisioning
- always disconnect the Python MetaTrader5 bridge after probe

R4 deliberately does not:

- enumerate saved MT5 account databases
- request or persist MT5 passwords
- log in to another trading account
- scan arbitrary disks for portable installations
- provision customer deployments
- issue setup handoff credentials
- mutate MT5 installation files
- install TODOBA EX5 artifacts
- purchase or migrate MetaTrader Virtual Hosting
- execute trades
- compose with the TODOBA Trading runtime

Standard discovery is read-only and does not initialize MT5.

Portable installations may later be supplied explicitly by the
customer-facing setup wizard. They are not auto-discovered.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import threading
from typing import Any


_STANDARD_VENDOR_DIRECTORY = "MetaQuotes"
_STANDARD_TERMINAL_DIRECTORY = "Terminal"
_STANDARD_ORIGIN_FILENAME = "origin.txt"
_TERMINAL_EXECUTABLE_NAME = "terminal64.exe"


@dataclass(
    frozen=True,
)
class CustomerMT5InstallationCandidate:
    """
    One read-only MT5 installation candidate discovered from
    the standard MetaTrader application-data structure.
    """

    installation_path: str
    terminal_path: str
    origin_path: str
    portable: bool

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "installation_path",
            self._normalize_required_path_string(
                self.installation_path,
                name="installation_path",
            ),
        )

        object.__setattr__(
            self,
            "terminal_path",
            self._normalize_required_path_string(
                self.terminal_path,
                name="terminal_path",
            ),
        )

        object.__setattr__(
            self,
            "origin_path",
            self._normalize_required_path_string(
                self.origin_path,
                name="origin_path",
            ),
        )

        if not isinstance(
            self.portable,
            bool,
        ):
            raise TypeError(
                "portable must be bool."
            )

    @staticmethod
    def _normalize_required_path_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized


@dataclass(
    frozen=True,
)
class CustomerMT5SetupPreflightResult:
    """
    Safe read-only result for one selected MT5 terminal.

    No MT5 password, customer identity, deployment identity,
    setup credential, or trading secret is represented here.
    """

    terminal_path: str
    installation_path: str
    data_path: str
    portable: bool
    login: int
    server: str
    margin_mode: int
    account_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "terminal_path",
            "installation_path",
            "data_path",
            "server",
            "account_fingerprint",
        ):
            value = getattr(
                self,
                field_name,
            )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{field_name} must be str."
                )

            if not value:
                raise ValueError(
                    f"{field_name} is required."
                )

        if not isinstance(
            self.portable,
            bool,
        ):
            raise TypeError(
                "portable must be bool."
            )

        if (
            not isinstance(
                self.login,
                int,
            )
            or isinstance(
                self.login,
                bool,
            )
        ):
            raise TypeError(
                "login must be int."
            )

        if self.login <= 0:
            raise ValueError(
                "login must be greater than zero."
            )

        if (
            not isinstance(
                self.margin_mode,
                int,
            )
            or isinstance(
                self.margin_mode,
                bool,
            )
        ):
            raise TypeError(
                "margin_mode must be int."
            )

        expected_fingerprint = (
            f"{self.server}:{self.login}"
        )

        if (
            self.account_fingerprint
            != expected_fingerprint
        ):
            raise ValueError(
                "account_fingerprint does not match "
                "server and login."
            )


class CustomerMT5SetupPreflightService:
    """
    Customer-side MT5 discovery and HEDGING preflight owner.

    MetaTrader5 Python bridge state is process-global enough
    that probes are serialized and always followed by shutdown.
    """

    def __init__(
        self,
        *,
        mt5_module: Any,
    ) -> None:
        if mt5_module is None:
            raise TypeError(
                "mt5_module is required."
            )

        for function_name in (
            "initialize",
            "shutdown",
            "terminal_info",
            "account_info",
        ):
            function = getattr(
                mt5_module,
                function_name,
                None,
            )

            if not callable(
                function
            ):
                raise TypeError(
                    "mt5_module must provide callable "
                    f"{function_name}()."
                )

        hedging_mode = getattr(
            mt5_module,
            "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
            None,
        )

        if (
            not isinstance(
                hedging_mode,
                int,
            )
            or isinstance(
                hedging_mode,
                bool,
            )
        ):
            raise TypeError(
                "mt5_module must expose integer "
                "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING."
            )

        self._mt5 = mt5_module
        self._hedging_margin_mode = (
            hedging_mode
        )
        self._probe_lock = threading.RLock()

    def discover_standard_installations(
        self,
        *,
        roaming_appdata_path: Path,
    ) -> tuple[
        CustomerMT5InstallationCandidate,
        ...,
    ]:
        """
        Discover standard MT5 installations without launching
        or attaching to MetaTrader.

        Invalid or stale origin entries are ignored rather than
        converted into unsafe candidates.
        """

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        terminal_root = (
            roaming_appdata_path
            / _STANDARD_VENDOR_DIRECTORY
            / _STANDARD_TERMINAL_DIRECTORY
        )

        if not terminal_root.exists():
            return ()

        if not terminal_root.is_dir():
            return ()

        discovered: dict[
            str,
            CustomerMT5InstallationCandidate,
        ] = {}

        try:
            instance_directories = tuple(
                sorted(
                    (
                        item
                        for item in terminal_root.iterdir()
                        if item.is_dir()
                    ),
                    key=lambda item: (
                        str(
                            item
                        ).casefold()
                    ),
                )
            )
        except OSError:
            return ()

        for instance_directory in (
            instance_directories
        ):
            origin_path = (
                instance_directory
                / _STANDARD_ORIGIN_FILENAME
            )

            if (
                not origin_path.exists()
                or not origin_path.is_file()
            ):
                continue

            installation_path = (
                self._read_origin_installation_path(
                    origin_path
                )
            )

            if installation_path is None:
                continue

            terminal_path = (
                installation_path
                / _TERMINAL_EXECUTABLE_NAME
            )

            if (
                not terminal_path.exists()
                or not terminal_path.is_file()
            ):
                continue

            try:
                normalized_installation_path = (
                    installation_path.resolve(
                        strict=True
                    )
                )

                normalized_terminal_path = (
                    terminal_path.resolve(
                        strict=True
                    )
                )

                normalized_origin_path = (
                    origin_path.resolve(
                        strict=True
                    )
                )
            except OSError:
                continue

            dedupe_key = (
                self._windows_path_key(
                    normalized_terminal_path
                )
            )

            if dedupe_key in discovered:
                continue

            discovered[
                dedupe_key
            ] = CustomerMT5InstallationCandidate(
                installation_path=str(
                    normalized_installation_path
                ),
                terminal_path=str(
                    normalized_terminal_path
                ),
                origin_path=str(
                    normalized_origin_path
                ),
                portable=False,
            )

        return tuple(
            discovered[
                key
            ]
            for key in sorted(
                discovered
            )
        )

    def preflight(
        self,
        *,
        terminal_path: Path,
        portable: bool,
    ) -> CustomerMT5SetupPreflightResult:
        """
        Probe exactly one customer-selected terminal.

        The selected terminal must already exist. R4 never
        supplies login/password/server credentials to MT5.

        The probe is valid only when:
        - MetaTrader5.initialize succeeds for the exact path
        - terminal_info is available
        - terminal_info.path matches the requested installation
        - terminal_info.data_path is a real directory
        - account_info is available
        - server is non-empty
        - login is positive
        - margin mode is RETAIL_HEDGING
        """

        normalized_terminal_path = (
            self._validate_selected_terminal_path(
                terminal_path
            )
        )

        if not isinstance(
            portable,
            bool,
        ):
            raise TypeError(
                "portable must be bool."
            )

        with self._probe_lock:
            initialize_attempted = False

            try:
                initialize_attempted = True

                initialized = bool(
                    self._mt5.initialize(
                        str(
                            normalized_terminal_path
                        ),
                        portable=portable,
                    )
                )

                if not initialized:
                    raise RuntimeError(
                        "Unable to initialize selected "
                        "MetaTrader 5 terminal."
                    )

                terminal_info = (
                    self._mt5.terminal_info()
                )

                if terminal_info is None:
                    raise RuntimeError(
                        "Unable to read selected "
                        "MetaTrader 5 terminal information."
                    )

                account_info = (
                    self._mt5.account_info()
                )

                if account_info is None:
                    raise RuntimeError(
                        "Selected MetaTrader 5 terminal "
                        "has no readable active account."
                    )

                return self._build_preflight_result(
                    selected_terminal_path=(
                        normalized_terminal_path
                    ),
                    portable=portable,
                    terminal_info=terminal_info,
                    account_info=account_info,
                )

            finally:
                if initialize_attempted:
                    self._mt5.shutdown()

    def _build_preflight_result(
        self,
        *,
        selected_terminal_path: Path,
        portable: bool,
        terminal_info: Any,
        account_info: Any,
    ) -> CustomerMT5SetupPreflightResult:
        reported_installation_path = (
            self._require_path_attribute(
                terminal_info,
                attribute_name="path",
                semantic_name=(
                    "terminal installation path"
                ),
            )
        )

        reported_data_path = (
            self._require_path_attribute(
                terminal_info,
                attribute_name="data_path",
                semantic_name="terminal data path",
            )
        )

        try:
            normalized_reported_installation = (
                reported_installation_path.resolve(
                    strict=True
                )
            )

            normalized_data_path = (
                reported_data_path.resolve(
                    strict=True
                )
            )
        except OSError as error:
            raise RuntimeError(
                "MetaTrader 5 reported an invalid "
                "terminal or data path."
            ) from error

        if not normalized_reported_installation.is_dir():
            raise RuntimeError(
                "MetaTrader 5 reported terminal path "
                "is not a directory."
            )

        if not normalized_data_path.is_dir():
            raise RuntimeError(
                "MetaTrader 5 reported data path "
                "is not a directory."
            )

        selected_installation_path = (
            selected_terminal_path.parent
        )

        if (
            self._windows_path_key(
                normalized_reported_installation
            )
            != self._windows_path_key(
                selected_installation_path
            )
        ):
            raise RuntimeError(
                "MetaTrader 5 initialized a different "
                "terminal than the selected installation."
            )

        server = getattr(
            account_info,
            "server",
            None,
        )

        if not isinstance(
            server,
            str,
        ):
            raise RuntimeError(
                "MetaTrader 5 account server is invalid."
            )

        if len(
            server
        ) == 0:
            raise RuntimeError(
                "MetaTrader 5 account server is empty."
            )

        login = getattr(
            account_info,
            "login",
            None,
        )

        if (
            not isinstance(
                login,
                int,
            )
            or isinstance(
                login,
                bool,
            )
            or login <= 0
        ):
            raise RuntimeError(
                "MetaTrader 5 account login is invalid."
            )

        margin_mode = getattr(
            account_info,
            "margin_mode",
            None,
        )

        if (
            not isinstance(
                margin_mode,
                int,
            )
            or isinstance(
                margin_mode,
                bool,
            )
        ):
            raise RuntimeError(
                "MetaTrader 5 account margin mode "
                "is invalid."
            )

        if (
            margin_mode
            != self._hedging_margin_mode
        ):
            raise ValueError(
                "TODOBA V1 requires an MT5 HEDGING "
                "account."
            )

        account_fingerprint = (
            f"{server}:{login}"
        )

        return CustomerMT5SetupPreflightResult(
            terminal_path=str(
                selected_terminal_path
            ),
            installation_path=str(
                normalized_reported_installation
            ),
            data_path=str(
                normalized_data_path
            ),
            portable=portable,
            login=login,
            server=server,
            margin_mode=margin_mode,
            account_fingerprint=(
                account_fingerprint
            ),
        )

    @staticmethod
    def _validate_selected_terminal_path(
        terminal_path: Path,
    ) -> Path:
        if not isinstance(
            terminal_path,
            Path,
        ):
            raise TypeError(
                "terminal_path must be Path."
            )

        if not terminal_path.exists():
            raise ValueError(
                "Selected MetaTrader 5 terminal "
                "does not exist."
            )

        if not terminal_path.is_file():
            raise ValueError(
                "Selected MetaTrader 5 terminal "
                "must be a file."
            )

        if (
            terminal_path.name.casefold()
            != _TERMINAL_EXECUTABLE_NAME.casefold()
        ):
            raise ValueError(
                "Selected MetaTrader 5 executable "
                "must be terminal64.exe."
            )

        try:
            return terminal_path.resolve(
                strict=True
            )
        except OSError as error:
            raise ValueError(
                "Selected MetaTrader 5 terminal "
                "path is invalid."
            ) from error

    @staticmethod
    def _require_path_attribute(
        source: Any,
        *,
        attribute_name: str,
        semantic_name: str,
    ) -> Path:
        value = getattr(
            source,
            attribute_name,
            None,
        )

        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError(
                f"MetaTrader 5 {semantic_name} "
                "is invalid."
            )

        if not value.strip():
            raise RuntimeError(
                f"MetaTrader 5 {semantic_name} "
                "is empty."
            )

        return Path(
            value
        )

    @staticmethod
    def _read_origin_installation_path(
        origin_path: Path,
    ) -> Path | None:
        """
        Read MetaTrader origin.txt conservatively.

        MetaTrader installations in the field may contain a BOM
        or use UTF-16LE. Support those common Windows encodings
        without changing the underlying path string.
        """

        try:
            payload = origin_path.read_bytes()
        except OSError:
            return None

        if not payload:
            return None

        text: str | None = None

        if (
            payload.startswith(
                b"\xff\xfe"
            )
            or payload.startswith(
                b"\xfe\xff"
            )
        ):
            try:
                text = payload.decode(
                    "utf-16"
                )
            except UnicodeError:
                return None
        else:
            try:
                text = payload.decode(
                    "utf-8-sig"
                )
            except UnicodeError:
                text = None

            if (
                text is not None
                and "\x00" in text
            ):
                try:
                    text = payload.decode(
                        "utf-16-le"
                    )
                except UnicodeError:
                    return None

        if text is None:
            return None

        normalized = text.strip()

        if not normalized:
            return None

        installation_path = Path(
            normalized
        )

        if not installation_path.exists():
            return None

        if not installation_path.is_dir():
            return None

        return installation_path

    @staticmethod
    def _windows_path_key(
        value: Path,
    ) -> str:
        """
        Use Windows-style case-insensitive path identity even
        when owner tests run on another operating system.
        """

        return os.path.normpath(
            str(
                value
            )
        ).replace(
            "/",
            "\\",
        ).casefold()