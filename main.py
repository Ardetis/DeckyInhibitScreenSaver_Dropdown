import asyncio
import decky_plugin
import queue
from settings import SettingsManager

def import_third_party_lib():
    import sys
    from pathlib import Path
    plugin_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(plugin_dir))
    sys.path.insert(0, str(plugin_dir.joinpath("lib")))
    sys.path.insert(0, str(plugin_dir.joinpath("py_modules")))

def setup_environ_vars():
    import os
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=/run/user/1000/bus'
    os.environ['HOME'] = '/home/deck'

import_third_party_lib()
setup_environ_vars()
settings_dir = decky_plugin.DECKY_PLUGIN_SETTINGS_DIR
settings = SettingsManager(name="settings", settings_directory=settings_dir)
event_queue = queue.Queue()

from dbus_next.aio import MessageBus
from dbus_next import Message, MessageType
from dbus_next.service import ServiceInterface, method, dbus_property, signal
from app_policies import PolicyRegistry
from portal_monitor import PortalInhibitMonitor
from mpris_monitor import MprisMonitor

bus = None
backend_start_lock = asyncio.Lock()
diagnostic_logging = False
effective_inhibited = False
pending_uninhibit_task = None
policy_registry = PolicyRegistry()
portal_monitor = None
mpris_monitor = None

class AppRequest:
    def __init__(self, sender, cookie, application, reason):
        self.sender = sender
        self.cookie = cookie
        self.application = application
        self.reason = reason
    
    async def is_connected(self):
        global bus
        message = Message(
            destination='org.freedesktop.DBus',
            path='/org/freedesktop/DBus',
            interface='org.freedesktop.DBus',
            member='GetConnectionUnixProcessID',
            signature='s',
            body=[self.sender]
        )
        reply = await bus.call(message)
        return reply.message_type != MessageType.ERROR


def diagnostic_log(message):
    if diagnostic_logging:
        decky_plugin.logger.info(message)


def log_diagnostic_snapshot():
    desired, grace_seconds, source = policy_registry.evaluate(
        BaseInterface.request_map.values()
    )
    diagnostic_log(
        f'[snapshot] backend_running={bus is not None} desired={desired} '
        f'effective={effective_inhibited} source={source} grace={grace_seconds} '
        f'active={len(BaseInterface.request_map)}'
    )
    for request in BaseInterface.request_map.values():
        diagnostic_log(
            f'[snapshot] inhibitor cookie={request.cookie} sender={request.sender} '
            f'application={request.application!r} reason={request.reason!r}'
        )
    if mpris_monitor is not None:
        for player in mpris_monitor.snapshot():
            diagnostic_log(
                f'[snapshot] mpris name={player["name"]} owner={player["owner"]} '
                f'status={player["status"]}'
            )


def schedule_policy_refresh(changed):
    if changed:
        asyncio.create_task(refresh_effective_inhibit_state())


def handle_portal_event(event, *args):
    if event == "inhibit":
        changed = policy_registry.on_portal_inhibit(*args)
    elif event == "close":
        changed = policy_registry.on_portal_close(*args)
    else:
        return
    schedule_policy_refresh(changed)


def handle_mpris_event(event, *args):
    if event == "appeared":
        changed = policy_registry.on_mpris_player_appeared(*args)
    elif event == "disappeared":
        changed = policy_registry.on_mpris_player_disappeared(*args)
    elif event == "playback":
        changed = policy_registry.on_mpris_playback(*args)
    else:
        return
    schedule_policy_refresh(changed)


async def start_portal_monitor():
    global portal_monitor
    if portal_monitor is None:
        portal_monitor = PortalInhibitMonitor(diagnostic_log, handle_portal_event)
    try:
        await portal_monitor.start()
    except Exception as error:
        diagnostic_log(f'[portal] monitor failed to start: {error}')


async def stop_portal_monitor():
    if portal_monitor is not None:
        await portal_monitor.stop()


async def start_mpris_monitor():
    global mpris_monitor
    if mpris_monitor is None:
        mpris_monitor = MprisMonitor(diagnostic_log, handle_mpris_event)
    try:
        await mpris_monitor.start()
    except Exception as error:
        diagnostic_log(f'[mpris] monitor failed to start: {error}')


async def stop_mpris_monitor():
    if mpris_monitor is not None:
        await mpris_monitor.stop()


async def start_runtime_monitors():
    await start_portal_monitor()
    await start_mpris_monitor()


async def stop_runtime_monitors():
    await stop_portal_monitor()
    await stop_mpris_monitor()


def cancel_pending_uninhibit():
    global pending_uninhibit_task
    task = pending_uninhibit_task
    pending_uninhibit_task = None
    if task is not None and task is not asyncio.current_task():
        task.cancel()


def set_effective_inhibited(value, source):
    global effective_inhibited
    if effective_inhibited == value:
        return
    effective_inhibited = value
    event_type = "Inhibit" if value else "UnInhibit"
    diagnostic_log(f'[policy] effective={value} source={source} event={event_type}')
    event_queue.put({"type": event_type})


async def finish_delayed_uninhibit(delay):
    global pending_uninhibit_task
    try:
        await asyncio.sleep(delay)
        pending_uninhibit_task = None
        desired, _, source = policy_registry.evaluate(BaseInterface.request_map.values())
        if not desired:
            set_effective_inhibited(False, f'{source}:grace-complete')
    except asyncio.CancelledError:
        pass


async def refresh_effective_inhibit_state():
    global pending_uninhibit_task
    desired, grace_seconds, source = policy_registry.evaluate(BaseInterface.request_map.values())
    diagnostic_log(
        f'[policy] desired={desired} effective={effective_inhibited} source={source} '
        f'grace={grace_seconds} active={len(BaseInterface.request_map)}'
    )

    if desired:
        cancel_pending_uninhibit()
        set_effective_inhibited(True, source)
        return

    if not effective_inhibited:
        cancel_pending_uninhibit()
        return

    if grace_seconds > 0:
        if pending_uninhibit_task is None:
            diagnostic_log(f'[policy] scheduling uninhibit in {grace_seconds}s')
            pending_uninhibit_task = asyncio.create_task(
                finish_delayed_uninhibit(grace_seconds)
            )
        return

    cancel_pending_uninhibit()
    set_effective_inhibited(False, source)


def reset_inhibit_state():
    global effective_inhibited
    cancel_pending_uninhibit()
    BaseInterface.request_map.clear()
    policy_registry.reset()
    effective_inhibited = False


class BaseInterface(ServiceInterface):
    ignore_application = ["Steam", "./steamwebhelper"]
    request_map = {}
    cookie = 0

    def __init__(self, service):
        super().__init__(service)

    async def _inhibit_impl(self, application, reason):
        if application in BaseInterface.ignore_application: return 0
        sender = ServiceInterface.last_msg.sender
        BaseInterface.cookie += 1
        cookie = BaseInterface.cookie
        BaseInterface.request_map[cookie] = AppRequest(sender, cookie, application, reason)
        diagnostic_log(
            f'[inhibit] acquired cookie={cookie} sender={sender} application={application!r} '
            f'reason={reason!r} active={len(BaseInterface.request_map)}'
        )
        await refresh_effective_inhibit_state()
        return cookie

    async def _un_inhibit_impl(self, cookie):
        if cookie == 0: return
        request = BaseInterface.request_map.pop(cookie, None)
        if request is None:
            diagnostic_log(
                f'[inhibit] release requested for unknown cookie={cookie} '
                f'active={len(BaseInterface.request_map)}'
            )
        else:
            diagnostic_log(
                f'[inhibit] released cookie={cookie} sender={request.sender} '
                f'application={request.application!r} reason={request.reason!r} '
                f'active={len(BaseInterface.request_map)}'
            )
        await refresh_effective_inhibit_state()


class InhibitInterface(BaseInterface):
    def __init__(self):
        super().__init__('org.freedesktop.ScreenSaver')

    @method()
    async def Inhibit(self, application: 's', reason: 's') -> 'u':
        return await self._inhibit_impl(application, reason)

    @method()
    async def UnInhibit(self, cookie: 'u'):
        return await self._un_inhibit_impl(cookie)

class PMInhibitInterface(BaseInterface):
    def __init__(self):
        super().__init__('org.freedesktop.PowerManagement.Inhibit')

    @method()
    async def Inhibit(self, application: 's', reason: 's') -> 'u':
        return await self._inhibit_impl(application, reason)

    @method()
    async def UnInhibit(self, cookie: 'u'):
        return await self._un_inhibit_impl(cookie)

class GnomeInterface(BaseInterface):
    def __init__(self):
        super().__init__('org.gnome.SessionManager')

    @method()
    async def Inhibit(self, application: 's', xid: 'u', reason: 's', flags: 'u') -> 'u':
        return await self._inhibit_impl(application, reason)

    @method()
    async def Uninhibit(self, cookie: 'u'):
        return await self._un_inhibit_impl(cookie)

async def stop_dbus():
    global bus
    try:
        await stop_runtime_monitors()
        if bus is not None:
            bus.disconnect()
        bus = None
        reset_inhibit_state()
    except Exception as e:
        decky_plugin.logger.info(f"error: {e}")

async def start_dbus():
    global bus
    async with backend_start_lock:
        if bus is not None:
            diagnostic_log("Backend already running; start skipped")
            return

        try:
            bus = await MessageBus().connect()
            interface = InhibitInterface()
            pm_interface = PMInhibitInterface()
            gnome_interface = GnomeInterface()
            bus.export('/ScreenSaver', interface) # vlc
            bus.export('/org/freedesktop/ScreenSaver', interface) # chrome
            bus.export('/org/freedesktop/PowerManagement/Inhibit', pm_interface) # wiliwili
            bus.export('/org/gnome/SessionManager', gnome_interface) # mpv with https://github.com/Guldoman/mpv_inhibit_gnome installed
            await bus.request_name('org.freedesktop.PowerManagement')
            await bus.request_name('org.freedesktop.ScreenSaver')
            await bus.request_name('org.gnome.SessionManager')
            await start_runtime_monitors()
            if diagnostic_logging:
                log_diagnostic_snapshot()
        except Exception as e:
            await stop_runtime_monitors()
            if bus is not None:
                bus.disconnect()
            bus = None
            reset_inhibit_state()
            decky_plugin.logger.info(f"error: {e}")

class Plugin:

    async def start_backend(self):
        diagnostic_log("Start backend server")
        await start_dbus()

    async def stop_backend(self):
        diagnostic_log("Stop backend server")
        was_inhibited = effective_inhibited
        await stop_dbus()
        event_queue.queue.clear()
        if was_inhibited:
            event_queue.put({"type": "UnInhibit"})

    async def is_running(self):
        global bus
        return bus is not None

    async def get_event(self):
        global bus
        res = []
        while not event_queue.empty():
            try:
                res.append(event_queue.get_nowait())
            except queue.Empty:
                continue
        if bus is not None and len(res) == 0:
            # Check closed D-Bus connections when there are no queued transitions.
            cookies = list(BaseInterface.request_map.keys())
            requests_changed = False
            for c in cookies:
                connected = await BaseInterface.request_map[c].is_connected()
                if not connected:
                    request = BaseInterface.request_map.pop(c)
                    diagnostic_log(
                        f'[inhibit] disconnected cookie={c} sender={request.sender} '
                        f'application={request.application!r} reason={request.reason!r} '
                        f'active={len(BaseInterface.request_map)}'
                    )
                    requests_changed = True
            if requests_changed:
                await refresh_effective_inhibit_state()

        # Always include authoritative state so a frontend reload or dropped
        # transition cannot leave Steam's power settings out of sync.
        res.append({"type": "InhibitState", "inhibited": effective_inhibited})
        return res

    async def get_settings(self, key: str, defaults):
        diagnostic_log('[settings] get {}'.format(key))
        return settings.getSetting(key, defaults)

    async def set_settings(self, key: str, value):
        global diagnostic_logging
        result = settings.setSetting(key, value)
        if key == "diagnostic_logging":
            diagnostic_logging = bool(value)
        diagnostic_log('[settings] set {}: {}'.format(key, value))
        if key == "diagnostic_logging" and diagnostic_logging:
            log_diagnostic_snapshot()
        return result

    async def write_diagnostic_log(self, level: str, message: str):
        diagnostic_log(f'[frontend:{level}] {message}')

    async def _main(self):
        global diagnostic_logging
        diagnostic_logging = bool(settings.getSetting("diagnostic_logging", False))
        diagnostic_log("Diagnostic logging enabled")

    async def _unload(self):
        diagnostic_log("Goodnight World!")
        await stop_dbus()

    async def _uninstall(self):
        pass

    async def _migration(self):
        pass