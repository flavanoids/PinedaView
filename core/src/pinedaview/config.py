# SPDX-License-Identifier: Apache-2.0
"""Typed configuration.

Precedence (highest first): constructor args → environment (``PINEDA_*``) →
``.env`` → the TOML config file → field defaults. Every value has a default, so a
config file is optional — a fresh server runs on New York weather until told
otherwise (that first question is the setup wizard's job, Phase 07).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

Units = Literal["imperial", "metric"]


class LocationConfig(BaseModel):
    """Where this server's weather, air quality, sun, and moon data come from."""

    query: str = "New York"
    """Free-form place for wttr.in — a city, a US ZIP, or ``"lat,lon"``."""

    label: str | None = None
    """Human-facing name. Falls back to what wttr.in reports for ``query``."""

    latitude: float | None = None
    longitude: float | None = None
    """Set explicitly to drive the NWS alerts point without waiting on a
    weather fetch. Otherwise filled in from wttr.in's nearest-area response."""


class ProviderConfig(BaseModel):
    """Polling cadence. Defaults match each upstream's own update rate —
    polling faster just re-fetches identical data."""

    weather_interval_s: int = Field(900, ge=60)
    air_quality_interval_s: int = Field(1800, ge=60)
    alerts_interval_s: int = Field(600, ge=60)
    moon_interval_s: int = Field(3600, ge=60)
    daily_content_interval_s: int = Field(3600, ge=60)
    indoor_climate_interval_s: int = Field(90, ge=60)
    calendar_interval_s: int = Field(900, ge=60)

    jitter_s: int = Field(90, ge=0)
    """Random 0..jitter_s added to each sleep so providers don't stampede."""

    retry_interval_s: int = Field(60, ge=5)
    """Sleep after a failed poll before trying again."""

    defer_interval_s: int = Field(5, ge=1)
    """Sleep after a poll returns ``None`` — a dependency isn't ready yet, so
    check back soon (air quality and alerts waiting on weather coordinates)."""

    http_timeout_s: float = Field(10.0, gt=0)
    user_agent: str = "PinedaView/1.0 (+https://github.com/flavanoids/PinedaView)"


class CountdownConfig(BaseModel):
    """An optional weekday-morning countdown that takes over the hero slot, then
    flashes an alert. Off by default — it is a PinedaDisplay ritual, not
    everyone's. Times are ``"HH:MM"`` local."""

    enabled: bool = False
    label: str = "Time to go"
    start: str = "07:30"
    end: str = "08:00"
    alert_seconds: int = Field(120, ge=0)
    weekdays_only: bool = True


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"  # a LAN dashboard server binds all interfaces by design
    port: int = Field(8090, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    db_path: Path = Path("data/pineda.db")
    write_token: str | None = None
    """If set, write endpoints and external ingest require this bearer token."""
    admin_token: str | None = None
    """If set, the admin surface (config, secrets, profiles/devices management,
    playback control, setup) requires this bearer token — on reads too. The
    public surface (view, stream, health, metrics, themes, photos, card list)
    stays open. Recommended whenever the LAN isn't fully trusted."""
    adopt_unknown_devices: bool = False
    """Register a screen this server has never seen under the id it asks for,
    instead of answering 404. For a primary/standby pair the kiosk fails over
    between: each server's database only knows the screens that paired with
    it, and the kiosk pins its id in the URL (``?device=``) so it stays the
    same screen on either. See docs/OPERATIONS.md#standby-server."""


class CalendarConfig(BaseModel):
    """Google Calendar OAuth. The client id/secret come from the operator's own
    Google Cloud project and live in the secret store (``google_calendar_client_id``
    / ``_client_secret``), not here — this only holds the one thing that can't be
    a secret: where the public bounce page redirects back to."""

    bounce_url: str | None = None
    """A static HTTPS page the operator hosts (see docs/INSTALL.md) whose only
    job is forwarding Google's ``?code=&state=`` back to this device's LAN
    address. Required because Google won't redirect to a bare LAN IP over
    plain HTTP. Connecting a calendar is unavailable until this is set."""


class MqttConfig(BaseModel):
    """Optional MQTT broker — lets a now-playing card read a PinedaDisplay /
    shairport-sync feed read-only, alongside the real display."""

    enabled: bool = False
    host: str = "localhost"
    port: int = Field(1883, ge=1, le=65535)
    topics: list[str] = Field(default_factory=lambda: ["airplaypi/#"])


class ControlConfig(BaseModel):
    """Where the restart-display / restart-system buttons act.

    Defaults to this machine (the historical single-host setup, where
    pineda-web and the kiosk are the same box). Set ``host`` when the server
    runs elsewhere (e.g. offloaded to a bigger machine) so the buttons still
    reach the actual kiosk device over SSH instead of restarting/rebooting
    whatever box happens to be running pineda-web.
    """

    host: str | None = None
    """SSH target for the kiosk device, e.g. "airplaypi". ``None`` means
    "this machine" — the buttons run systemctl locally, as before."""
    user: str = "pineda"
    ssh_key: Path | None = None
    """Private key for ``user@host``. Must be authorized on the kiosk device
    for exactly ``systemctl restart pineda-kiosk.service`` and ``systemctl
    reboot`` — see docs/OPERATIONS.md#split-host-control."""
    kiosk_service: str = "pinedaview-kiosk.service"
    pin: str | None = None
    """Digits the phone menu asks for before restarting the display or the
    device — keeps a guest who scanned the QR from rebooting it unannounced.
    Not a secret worth the name; ``None`` asks for nothing."""
    screen: str | None = None
    """The kiosk's device id. A browser pairing from ``host``'s address gets
    this id back instead of a new screen (clearing the kiosk's cache no longer
    makes it a stranger), it's always kept, and only it has a live snapshot."""


class AntiguaConfig(BaseModel):
    """The voice assistant, which keeps the household's alarms and reminders.
    The phone menu lists, sets and switches them through it (see
    :mod:`pinedaview.alarms`)."""

    url: str | None = None
    """Antigua's HTTP server, e.g. "http://127.0.0.1:9393". ``None``: the
    menu's alarm list says it isn't connected."""
    fallback_url: str | None = None
    """Antigua's fallback server, asked when ``url`` doesn't answer (or says
    the other one has them): e.g. "http://10.77.0.3:9394"."""


class StandbyConfig(BaseModel):
    """Set on a standby box only (see :mod:`pinedaview.standby`)."""

    primary: str | None = None
    """The primary pineda-web, e.g. "http://192.0.2.171:8090"."""


class CamerasConfig(BaseModel):
    """Live video for the camera takeover, relayed from a go2rtc server.

    Home Assistant's eufy_security pushes a camera's P2P livestream into
    go2rtc while it runs (this server starts and stops it when ``ha_url`` is
    set); the kiosk plays it through /api/cameras/{name}/stream.mp4, and only
    while that camera's takeover is up."""

    go2rtc: str = "http://127.0.0.1:1984"
    streams: dict[str, str] = Field(default_factory=dict)
    """Camera name → go2rtc stream name, e.g. front_door = "T8210P00203706DA"."""
    snapshots_dir: Path | None = None
    """Where Antigua leaves each camera's latest photo (``front_door.jpg``)
    and a ``front_door.json`` beside it (title, when, how often, battery).
    The home-cams card shows them."""
    always_battery: list[str] = Field(default_factory=list)
    """Cameras whose battery the home-cams card always shows on that camera's
    photo, not only when it's low — the doorbell; a solar-charged camera doesn't."""
    titles: dict[str, str] = Field(default_factory=dict)
    """Camera name → what the card calls it: front_door = "Front door"."""
    entities: dict[str, str] = Field(default_factory=dict)
    """Camera name → its Home Assistant camera entity (front_door =
    "camera.doorbell"). With ``ha_url`` set, this server starts a camera's
    livestream when its card goes up and stops it when the card comes down."""
    ha_url: str | None = None
    """Home Assistant, e.g. "http://192.0.2.102:8123". ``None``: whoever
    puts a camera card up starts and stops the livestream itself."""
    ha_token_file: Path | None = None
    """A file holding ``HA_TOKEN=...`` (readable by this server only)."""


class McpClientConfig(BaseModel):
    token_sha256: str
    """The SHA-256 of the client's bearer token, hex — never the token itself
    (``pineda-web mcp-token <name>`` makes one)."""
    scopes: list[str] = Field(default_factory=list)
    """What it may call: display:read, display:write, system, camera:view."""


class McpConfig(BaseModel):
    """The MCP server at /mcp (see docs/MCP.md): the display, its takeovers
    and the cameras, for a voice assistant. Unlike the REST API, every call
    needs a client's bearer token."""

    enabled: bool = True
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1:*", "localhost:*"])
    """Host headers accepted (others get 421 — DNS rebinding); "host:*" for any port."""
    profile: str = "default"
    """The profile whose theme the display tools read and set."""
    clients: dict[str, McpClientConfig] = Field(default_factory=dict)


class UpdateConfig(BaseModel):
    """Automatic updates configuration for PinedaView."""

    enabled: bool = True
    target_branch: str = "main"
    deploy_key: Path | None = None
    runner_cmd: str = "/usr/local/bin/pinedaview-update"


class Settings(BaseSettings):
    """Root configuration object."""

    model_config = SettingsConfigDict(
        env_prefix="PINEDA_",
        env_nested_delimiter="__",
        env_file=".env",
        toml_file="config.toml",
        extra="ignore",
    )

    location: LocationConfig = LocationConfig()
    providers: ProviderConfig = ProviderConfig()
    api: ApiConfig = ApiConfig()
    mqtt: MqttConfig = MqttConfig()
    control: ControlConfig = ControlConfig()
    update: UpdateConfig = UpdateConfig()
    calendar: CalendarConfig = CalendarConfig()
    countdown: CountdownConfig = CountdownConfig()
    cameras: CamerasConfig = CamerasConfig()
    mcp: McpConfig = McpConfig()
    antigua: AntiguaConfig = AntiguaConfig()
    standby: StandbyConfig = StandbyConfig()
    units: Units = "imperial"
    theme: str = "blush"
    setup_complete: bool = False
    """Flipped true when the first-run wizard finishes (or a config file exists)."""
    config_file: Path = Path("config.toml")
    """Where the wizard writes the config that marks setup done."""

    state_dir: Path = Path("data")
    """Where mutable runtime state (affirmation history, secrets, the db) lives."""

    cards_dir: Path = Path("cards")
    """User card folders — additive to the built-ins, may override by id."""
    themes_dir: Path = Path("themes")
    """User theme files (.toml or .json) — additive to the built-ins."""
    disabled_cards: list[str] = Field(default_factory=lambda: ["commute", "phrase", "moon-climate"])
    """"commute" ships disabled by default: it polls the Google Directions
    API (maps.googleapis.com) with departure_time=now for every configured
    stop, every 4 minutes — the live-traffic tier, which is billed and ran
    up a real charge. The code stays in the repo (providers/commute.py,
    cards/builtin/commute/) for anyone who wants to opt back in deliberately
    — remove "commute" from this list and set the google_maps secret.

    "phrase" (the multilingual word of the day) is retired: while it's listed
    here, startup moves the traffic cams into its slot on every saved stack
    (Registry.retire_card).

    "moon-climate" (moon phase + indoor temperature) is retired the same
    way: the home cameras take its slot."""
    photos_dir: Path = Path("data/photos")

    debug_http: bool = False
    debug_port: int = Field(8099, ge=0, le=65535)
    """0 lets the OS pick a free port (handy in tests)."""
    log_level: str = "INFO"
    log_json: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


_SYSTEM_CONFIG = Path("/etc/pineda-web/config.toml")


def _discover_config() -> Path | None:
    """Find a config file when the CLI didn't name one.

    Order: ``$PINEDA_CONFIG_FILE`` → ``./config.toml`` → ``/etc/pineda-web/config.toml``.
    Environment variables and CLI flags still win over whatever it finds.
    """
    env_path = os.environ.get("PINEDA_CONFIG_FILE")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    if Path("config.toml").is_file():
        return None  # the default source already reads ./config.toml
    if _SYSTEM_CONFIG.is_file():
        return _SYSTEM_CONFIG
    return None


def load_settings(
    config_path: Path | None = None,
    *,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Build :class:`Settings`.

    ``config_path`` points at a specific TOML file; ``overrides`` (typically from
    CLI flags) take precedence over every other source.
    """
    kwargs = overrides or {}
    if config_path is None:
        config_path = _discover_config()
    if config_path is None:
        settings = Settings(**kwargs)
        settings.setup_complete = settings.setup_complete or Path("config.toml").exists()
        return settings

    class _Scoped(Settings):
        model_config = SettingsConfigDict(
            **{**Settings.model_config, "toml_file": str(config_path)}
        )

    scoped = _Scoped(**kwargs)
    scoped.setup_complete = scoped.setup_complete or config_path.exists()
    return scoped
